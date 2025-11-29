from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime

from app.enums.sold_status import SoldStatus 
from app.models.categories_models import Category

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class ReviewResponse(BaseModel):
    id: int
    rating: int
    comment: Optional[str]
    created_at: datetime
    user_name: str

    class Config:
        from_attributes = True


class RegisterGiftCardInfo(BaseModel):
    title: str
    valor: Decimal
    imageUrl: Optional[str] = None

    class Config:
        from_attributes = True


class RegisterGiftCard(BaseModel):
    id: Optional[UUID] = None
    user_id: int
    title: str
    valor: Decimal
    desired_amount: Decimal
    ativo: bool = True
    validade: Optional[date] = None
    description: Optional[str] = None
    quantityavailable: int
    generaterandomly: bool = False
    codes: Optional[str] = None
    imageUrl: Optional[str] = None
    category_id: Optional[int] = None
    category: Optional[Category] = None
    has_sales: bool = False
    average_rating: float = 0.0
    total_reviews: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SoldGiftCard(BaseModel):
    id: UUID
    code: str
    status: SoldStatus 
    purchase_date: date
    register_giftcard_id: UUID
    owner_id: int
    nota: Optional[int] = None
    
    original_giftcard: RegisterGiftCardInfo

    class Config:
        from_attributes = True

class SoldGiftCardDetails(SoldGiftCard):
    owner_name: str