import uuid
from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    CHAR, TypeDecorator, Numeric, Date, DateTime, Enum as SqlEnum
)
from sqlalchemy.orm import relationship
from app.database.db_config import Base, now_brt
from datetime import datetime

from app.enums.sold_status import SoldStatus

class GUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None: return value
        return str(value)
    def process_result_value(self, value, dialect):
        if value is None: return value
        try:
            return uuid.UUID(value)
        except (ValueError, TypeError):
            return value

class RegisterGiftCardORM(Base):
    __tablename__ = "register_giftcards"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(100), nullable=False)
    desired_amount = Column(Numeric(10, 2), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    validade = Column(Date, nullable=True)
    description = Column(String(255), nullable=True)
    quantityavailable = Column(Integer, nullable=False)
    generaterandomly = Column(Boolean, default=False)
    codes = Column(String(1000), nullable=True) 
    imageUrl = Column(String(255), nullable=True)
    low_stock_notified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=now_brt)
    updated_at = Column(DateTime, default=now_brt, onupdate=now_brt)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("CategoriesORM")

    user = relationship("UserORM", back_populates="giftcards")
    sold_cards = relationship("SoldGiftCardORM", back_populates="original_giftcard", cascade="all, delete-orphan")
    
    reviews = relationship("GiftCardReviewORM", back_populates="giftcard", cascade="all, delete-orphan")

    @property
    def has_sales(self):
        return len(self.sold_cards) > 0

    @property
    def average_rating(self):
        if not self.reviews:
            return 0.0
        total = sum(r.rating for r in self.reviews)
        return round(total / len(self.reviews), 1)

    @property
    def total_reviews(self):
        return len(self.reviews)


class GiftCardReviewORM(Base):
    __tablename__ = "giftcard_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    giftcard_id = Column(GUID(), ForeignKey("register_giftcards.id"), nullable=False)
    rating = Column(Integer, nullable=False) # 1 a 5
    comment = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=now_brt)

    user = relationship("UserORM")
    giftcard = relationship("RegisterGiftCardORM", back_populates="reviews")


class SoldGiftCardORM(Base):
    __tablename__ = "sold_giftcards"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(SqlEnum(SoldStatus), nullable=False, default=SoldStatus.VALID)
    purchase_date = Column(DateTime, default=now_brt)

    nota = Column(Integer, nullable=True) 

    register_giftcard_id = Column(GUID(), ForeignKey("register_giftcards.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    transaction_id = Column(String(255), index=True, nullable=True)

    original_giftcard = relationship("RegisterGiftCardORM", back_populates="sold_cards")
    owner = relationship("UserORM", back_populates="purchased_giftcards")