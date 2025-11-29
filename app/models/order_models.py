from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from .order_orm import OrderStatus, OrderItemStatus

# --- NOVO: Schema para visualização do presente (SEM CÓDIGOS) ---
class OrderGiftItemSchema(BaseModel):
    recipient_name: str
    quantity: int
    # Não incluímos 'codes' nem 'message' aqui se não for necessário

    class Config:
        from_attributes = True

# Define quais informações do Gift Card original devem ser incluídas
class GiftCardInfo(BaseModel):
    title: str
    imageUrl: Optional[str] = None
    valor: Decimal # Preço de venda

    class Config:
        from_attributes = True

# Define quais informações do Dono (Comprador) incluir
class OwnerInfo(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

# Define a estrutura do Pedido DENTRO do Item
class OrderInfoForOrderItem(BaseModel):
    owner_id: int
    created_at: datetime
    status: OrderStatus
    owner: Optional[OwnerInfo] = None 

    class Config:
        from_attributes = True

# Schema principal para um Item de Pedido (usado na resposta da API)
class OrderItemSchema(BaseModel): 
    id: UUID
    register_giftcard_id: UUID
    enterprise_id: int
    quantity: int
    unit_price: Decimal 
    seller_amount: Decimal 
    final_giftcard_codes: Optional[str] = None
    used_codes: Optional[str] = None
    status: OrderItemStatus 
    original_giftcard: GiftCardInfo 
    order: Optional[OrderInfoForOrderItem] = None 
    user_rating: Optional[int] = None
    
    # --- NOVO: Lista de presentes vinculada ao item ---
    gift_items: List[OrderGiftItemSchema] = []

    class Config:
        from_attributes = True


class OrderSchema(BaseModel): 
    id: UUID
    owner_id: int
    status: OrderStatus 
    total_amount: Decimal 
    net_amount: Optional[Decimal] = None
    created_at: datetime
    items: List[OrderItemSchema] = [] 
    owner: Optional[OwnerInfo] = None 

    class Config:
        from_attributes = True