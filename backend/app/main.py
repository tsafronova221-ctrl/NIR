from collections.abc import Sequence

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    resolve_user_from_token,
    verify_bot_token,
)
from .config import get_settings
from .crud import (
    cancel_purchase,
    check_flag_completion,
    confirm_purchase,
    create_pending_purchase,
    ensure_user,
    get_product,
    get_pending_purchase,
    get_confirmed_quantities_by_product,
    list_user_purchases,
    list_products,
    clear_user_state,
    PURCHASE_STATUS_CONFIRMED,
    seed_default_products,
)
from .database import Base, SessionLocal, engine, get_session
from .models import User
from .schemas import (
    OrderResponse,
    PendingPurchaseResponse,
    PurchaseListResponse,
    ProductRead,
    PurchaseRead,
    PurchaseRequest,
    RewardUnlock,
    TokenResponse,
    TokenVerifyRequest,
    UserCreate,
    UserRead,
)

settings = get_settings()


def _normalize_origins(origins: Sequence[str]) -> list[str]:
    if not origins:
        return ["*"]
    if len(origins) == 1 and origins[0] == "*":
        return ["*"]
    return list(origins)


app = FastAPI(title="Planner Backend", version="0.1.0")

origins = _normalize_origins(settings.BACKEND_CORS_ORIGINS)
allow_all = origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else origins,
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        seed_default_products(session)
    finally:
        session.close()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/users/login", response_model=TokenResponse)
def login_user(
    payload: UserCreate,
    db: Session = Depends(get_session),
) -> TokenResponse:
    user = ensure_user(db, payload.user_id)
    token = create_access_token(user_id=user.id)
    return TokenResponse(token=token, user=UserRead.model_validate(user))


@app.get("/users/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@app.post("/auth/verify", response_model=UserRead)
def verify_token(
    payload: TokenVerifyRequest,
    db: Session = Depends(get_session),
) -> UserRead:
    user = resolve_user_from_token(payload.token, db)
    return UserRead.model_validate(user)


@app.post("/users/clear", response_model=UserRead)
def clear_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> UserRead:
    user = clear_user_state(db, user=current_user)
    return UserRead.model_validate(user)


@app.get("/products", response_model=list[ProductRead])
def read_products(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[ProductRead]:
    products = list_products(db)
    owned_quantities = get_confirmed_quantities_by_product(db, current_user)
    payload: list[ProductRead] = []
    for product in products:
        item = ProductRead.model_validate(product)
        item.owned_quantity = owned_quantities.get(product.id, 0)
        if product.name == settings.FLAG_PART_PRODUCT_NAME:
            item.max_per_user = settings.FLAG_PARTS_REQUIRED
        else:
            item.max_per_user = 1
        payload.append(item)
    return payload


@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> OrderResponse:
    product = get_product(db, payload.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")

    total_price = product.price * payload.quantity
    if current_user.balance < total_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недостаточно средств для покупки.",
        )

    try:
        purchase = create_pending_purchase(
            db,
            user=current_user,
            product=product,
            quantity=payload.quantity,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    db.refresh(current_user)

    return OrderResponse(
        user=UserRead.model_validate(current_user),
        purchase=PurchaseRead.model_validate(purchase),
    )


@app.get("/orders/pending", response_model=PendingPurchaseResponse)
def read_pending_order(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PendingPurchaseResponse:
    purchase = get_pending_purchase(db, current_user)
    if purchase is None:
        return PendingPurchaseResponse(purchase=None)

    return PendingPurchaseResponse(
        purchase=PurchaseRead.model_validate(purchase),
    )


@app.get("/orders/history", response_model=PurchaseListResponse)
def read_purchase_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> PurchaseListResponse:
    purchases = list_user_purchases(
        db,
        current_user,
        status=PURCHASE_STATUS_CONFIRMED,
    )
    return PurchaseListResponse(
        purchases=[PurchaseRead.model_validate(item) for item in purchases]
    )


@app.post("/orders/confirm", response_model=OrderResponse)
def confirm_pending_order(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> OrderResponse:
    purchase = get_pending_purchase(db, current_user)
    if purchase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Нет покупок, ожидающих подтверждения.",
        )

    override_total = request.headers.get("x-planner-locked-amount")
    bot_token = request.headers.get("x-planner-bot-token")

    if override_total is not None:
        verify_bot_token(bot_token)

    try:
        purchase = confirm_purchase(
            db,
            purchase=purchase,
            override_total=override_total,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    reward_data = check_flag_completion(db, purchase=purchase)

    db.refresh(current_user)

    return OrderResponse(
        user=UserRead.model_validate(current_user),
        purchase=PurchaseRead.model_validate(purchase),
        reward=RewardUnlock(**reward_data) if reward_data else None,
    )


@app.post("/orders/cancel", response_model=OrderResponse)
def cancel_pending_order(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> OrderResponse:
    purchase = get_pending_purchase(db, current_user)
    if purchase is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Нет покупок, ожидающих подтверждения.",
        )

    try:
        purchase = cancel_purchase(db, purchase=purchase)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    db.refresh(current_user)

    return OrderResponse(
        user=UserRead.model_validate(current_user),
        purchase=PurchaseRead.model_validate(purchase),
    )
