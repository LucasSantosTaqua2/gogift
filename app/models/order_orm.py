import uuid
from sqlalchemy import (
    Column, Integer, String, ForeignKey, Numeric, DateTime, Enum as SqlEnum
)
from sqlalchemy.orm import relationship
from app.database.db_config import Base, now_brt
from datetime import datetime
from app.models.giftcard_orm import GUID
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REFUNDED = "REFUNDED"

class OrderItemStatus(str, Enum):
    VALID = "VALID"     
    USED = "USED"       
    PARTIALLY_USED = "PARTIALLY_USED" 

class OrderORM(Base):
    __tablename__ = "orders"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(SqlEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    total_amount = Column(Numeric(10, 2), nullable=False)
    net_amount = Column(Numeric(10, 2), nullable=True)
    mercadopago_transaction_id = Column(String(255), index=True, nullable=True)
    created_at = Column(DateTime, default=now_brt) 
    updated_at = Column(DateTime, default=now_brt, onupdate=now_brt)

    owner = relationship("UserORM", back_populates="orders")
    items = relationship("OrderItemORM", back_populates="order", cascade="all, delete-orphan")

class OrderItemORM(Base):
    __tablename__ = "order_items"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id = Column(GUID(), ForeignKey("orders.id"), nullable=False)
    register_giftcard_id = Column(GUID(), ForeignKey("register_giftcards.id"), nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprise.id"), nullable=False, index=True)
    
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    seller_amount = Column(Numeric(10, 2), nullable=False)

    final_giftcard_codes = Column(String(1000), nullable=True) 
    used_codes = Column(String(1000), nullable=True)
    status = Column(SqlEnum(OrderItemStatus), nullable=False, default=OrderItemStatus.VALID)
    
    order = relationship("OrderORM", back_populates="items")
    original_giftcard = relationship("RegisterGiftCardORM")
    enterprise = relationship("EmpresaORM")

    gift_items = relationship("OrderGiftItemORM", back_populates="order_item", cascade="all, delete-orphan")

class OrderGiftItemORM(Base):
    __tablename__ = "order_gift_items"

    id = Column(Integer, primary_key=True, index=True)
    order_item_id = Column(GUID(), ForeignKey("order_items.id"), nullable=False)
    
    recipient_name = Column(String(100), nullable=False)
    recipient_email = Column(String(100), nullable=False)
    message = Column(String(500), nullable=True) 
    quantity = Column(Integer, nullable=False)  
    
    codes = Column(String(1000), nullable=True) 

    order_item = relationship("OrderItemORM", back_populates="gift_items")