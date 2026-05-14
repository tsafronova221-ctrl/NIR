from datetime import datetime
from typing import NotRequired, TypedDict

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .models import Product, Purchase, User


DEFAULT_USER_BALANCE = 1000


class SeedProduct(TypedDict):
    name: str
    price: int
    description: NotRequired[str]
    image_url: NotRequired[str]

settings = get_settings()

DEFAULT_PRODUCTS: list[SeedProduct] = [
    {
        "name": "Часть флага",
        "description": "Эксклюзивный фрагмент легендарного флага сообщества.",
        "price": 500,
        "image_url": "https://storage.vsemayki.ru/images/0/2/2942/2942527/previews/people_2_flag_auto_front_white_250.jpg",
    },
    {
        "name": "Картинка",
        "description": "Высококачественное изображение с авторской обработкой.",
        "price": 50,
        "image_url": "https://i.pinimg.com/736x/ff/1b/bf/ff1bbffc7465d6799b47f1686a424d86.jpg",
    },
    {
        "name": "Видео",
        "description": "Короткий ролик с уникальными эффектами и озвучкой.",
        "price": 100,
        "image_url": "https://images.steamusercontent.com/ugc/13492491364307202296/5ADE24137AD1513BD916A34D69E45849E785C8AE/?imw=512&amp;imh=288&amp;ima=fit&amp;impolicy=Letterbox&amp;imcolor=%23000000&amp;letterbox=true",
    },
]


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, user_id: int, initial_balance: int = 1000) -> User:
    user = User(id=user_id, balance=initial_balance)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_user(db: Session, user_id: int, initial_balance: int = 1000) -> User:
    user = get_user(db, user_id)
    if user is None:
        user = create_user(db, user_id, initial_balance=initial_balance)
    return user


def list_products(db: Session) -> list[Product]:
    return db.query(Product).order_by(Product.id).all()


def get_product(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def seed_default_products(db: Session) -> None:
    existing_products = {product.name: product for product in db.query(Product).all()}
    desired_names = {product_data["name"] for product_data in DEFAULT_PRODUCTS}

    for product_data in DEFAULT_PRODUCTS:
        product = existing_products.get(product_data["name"])
        if product is None:
            product = Product(**product_data)
            db.add(product)
        else:
            product.description = product_data.get("description")
            product.price = product_data["price"]
            product.image_url = product_data.get("image_url")

    for product in db.query(Product).filter(~Product.name.in_(desired_names)).all():
        db.delete(product)

    db.commit()


PURCHASE_STATUS_PENDING = "pending"
PURCHASE_STATUS_CONFIRMED = "confirmed"
PURCHASE_STATUS_CANCELLED = "cancelled"


def get_pending_purchase(db: Session, user: User) -> Purchase | None:
    return (
        db.query(Purchase)
        .filter(
            Purchase.user_id == user.id,
            Purchase.status == PURCHASE_STATUS_PENDING,
        )
        .order_by(Purchase.created_at.desc())
        .first()
    )


def get_purchase(db: Session, purchase_id: int) -> Purchase | None:
    return db.get(Purchase, purchase_id)


def list_user_purchases(
    db: Session,
    user: User,
    *,
    status: str | None = None,
) -> list[Purchase]:
    query = (
        db.query(Purchase)
        .options(joinedload(Purchase.product))
        .filter(Purchase.user_id == user.id)
        .order_by(Purchase.created_at.desc())
    )
    if status is not None:
        query = query.filter(Purchase.status == status)
    return query.all()


def get_confirmed_quantities_by_product(db: Session, user: User) -> dict[int, int]:
    rows = (
        db.query(Purchase.product_id, func.coalesce(func.sum(Purchase.quantity), 0))
        .filter(
            Purchase.user_id == user.id,
            Purchase.status == PURCHASE_STATUS_CONFIRMED,
        )
        .group_by(Purchase.product_id)
        .all()
    )
    return {product_id: int(total or 0) for product_id, total in rows}


def create_pending_purchase(
    db: Session,
    *,
    user: User,
    product: Product,
    quantity: int,
) -> Purchase:
    if quantity <= 0:
        raise ValueError("Количество должно быть положительным.")

    if user.frozen_balance > 0 or get_pending_purchase(db, user) is not None:
        raise ValueError("У пользователя уже есть неподтверждённая покупка.")

    total_price = product.price * quantity
    available = user.balance - user.frozen_balance
    if available < total_price:
        raise ValueError("Недостаточно средств для покупки.")

    confirmed_quantities = get_confirmed_quantities_by_product(db, user)
    current_confirmed = confirmed_quantities.get(product.id, 0)

    if product.name == settings.FLAG_PART_PRODUCT_NAME:
        max_parts = settings.FLAG_PARTS_REQUIRED
        if max_parts <= 0:
            raise ValueError("Некорректная конфигурация количества частей флага.")
        if current_confirmed >= max_parts:
            raise ValueError("Вы уже собрали все части флага.")
        if current_confirmed + quantity > max_parts:
            raise ValueError("Запрошенное количество превышает доступное число частей.")
    else:
        if current_confirmed > 0:
            raise ValueError("Этот продукт уже добавлен в вашу коллекцию.")

    purchase = Purchase(
        user=user,
        product=product,
        quantity=quantity,
        total_price=total_price,
        status=PURCHASE_STATUS_PENDING,
    )
    db.add(purchase)
    user.frozen_balance = total_price
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(purchase)
    return purchase


def confirm_purchase(
    db: Session,
    *,
    purchase: Purchase,
    override_total: int | float | None = None,
) -> Purchase:
    if purchase.status != PURCHASE_STATUS_PENDING:
        raise ValueError("Покупка уже обработана.")

    user = purchase.user
    total_price = purchase.total_price

    if override_total is not None:
        try:
            candidate = float(override_total)
            if candidate >= 0:
                total_price = int(candidate)
        except (TypeError, ValueError):
            pass

    if user.balance < total_price:
        raise ValueError("Недостаточно средств для подтверждения покупки.")

    user.balance -= total_price
    user.frozen_balance = 0
    purchase.total_price = total_price
    purchase.status = PURCHASE_STATUS_CONFIRMED
    purchase.processed_at = datetime.utcnow()

    db.add(user)
    db.add(purchase)
    db.commit()
    db.refresh(user)
    db.refresh(purchase)
    return purchase


def check_flag_completion(
    db: Session,
    *,
    purchase: Purchase,
) -> dict[str, str] | None:
    product = purchase.product
    user = purchase.user

    if product.name != settings.FLAG_PART_PRODUCT_NAME:
        return None

    total_parts = get_confirmed_quantities_by_product(db, user).get(product.id, 0)
    if total_parts < settings.FLAG_PARTS_REQUIRED:
        return None

    if user.flag_awarded:
        return None

    user.flag_awarded = True
    user.flag_awarded_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "name": settings.FLAG_REWARD_NAME,
        "message": settings.FLAG_REWARD_MESSAGE,
    }


def cancel_purchase(db: Session, *, purchase: Purchase) -> Purchase:
    if purchase.status != PURCHASE_STATUS_PENDING:
        raise ValueError("Покупка уже обработана.")

    user = purchase.user
    user.frozen_balance = 0
    purchase.status = PURCHASE_STATUS_CANCELLED
    purchase.processed_at = datetime.utcnow()

    db.add(user)
    db.add(purchase)
    db.commit()
    db.refresh(user)
    db.refresh(purchase)
    return purchase


def clear_user_state(db: Session, *, user: User) -> User:
    db.query(Purchase).filter(Purchase.user_id == user.id).delete(
        synchronize_session=False
    )

    user.balance = DEFAULT_USER_BALANCE
    user.frozen_balance = 0
    user.flag_awarded = False
    user.flag_awarded_at = None

    db.add(user)
    db.commit()
    db.refresh(user)
    return user
