from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    user_id: int


class UserRead(BaseModel):
    id: int
    balance: int
    frozen_balance: int
    flag_awarded: bool
    flag_awarded_at: datetime | None = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    token: str
    user: UserRead


class TokenVerifyRequest(BaseModel):
    token: str


class ProductRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    price: int
    image_url: str | None = None
    owned_quantity: int = 0
    max_per_user: int | None = None

    class Config:
        from_attributes = True


class PurchaseRequest(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, default=1)


class PurchaseRead(BaseModel):
    id: int
    product: ProductRead
    quantity: int
    total_price: int
    created_at: datetime
    status: str
    processed_at: datetime | None = None

    class Config:
        from_attributes = True


class RewardUnlock(BaseModel):
    name: str
    message: str


class OrderResponse(BaseModel):
    user: UserRead
    purchase: PurchaseRead
    reward: RewardUnlock | None = None


class PendingPurchaseResponse(BaseModel):
    purchase: PurchaseRead | None = None


class PurchaseListResponse(BaseModel):
    purchases: list[PurchaseRead]
