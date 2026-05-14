from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=False)
    balance = Column(Integer, nullable=False, default=1000)
    frozen_balance = Column(Integer, nullable=False, default=0)
    flag_awarded = Column(Boolean, nullable=False, default=False)
    flag_awarded_at = Column(DateTime, nullable=True)
    purchases = relationship("Purchase", back_populates="user", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    price = Column(Integer, nullable=False)  # stored in minor units (e.g. cents)
    image_url = Column(String(500), nullable=True)
    purchases = relationship("Purchase", back_populates="product", cascade="all, delete-orphan")


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    total_price = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    processed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="purchases")
    product = relationship("Product", back_populates="purchases")
