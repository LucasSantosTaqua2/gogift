from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.auth.auth_bearer import get_current_admin
from app.database.db_config import get_db
from app.models.giftcard_orm import GiftCardReviewORM
from app.security import get_current_user
from app.models.user_orm import UserORM
from app.models.order_orm import OrderORM, OrderItemORM 
from app.models.order_models import OrderSchema

router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)

@router.get("/me", response_model=List[OrderSchema])
async def get_my_orders(
    db: Session = Depends(get_db),
    current_user: UserORM = Depends(get_current_user)
):
    # 1. Busca os pedidos
    orders = db.query(OrderORM).options(
        joinedload(OrderORM.items).joinedload(OrderItemORM.original_giftcard),
        joinedload(OrderORM.items).joinedload(OrderItemORM.enterprise),
        # --- ATUALIZAÇÃO: Carrega os presentes ---
        joinedload(OrderORM.items).joinedload(OrderItemORM.gift_items) 
    ).filter(
        OrderORM.owner_id == current_user.id
    ).order_by(
        OrderORM.created_at.desc()
    ).all()

    user_reviews = db.query(GiftCardReviewORM).filter(
        GiftCardReviewORM.user_id == current_user.id
    ).all()
    
    reviews_map = {review.giftcard_id: review.rating for review in user_reviews}

    for order in orders:
        for item in order.items:
            rating = reviews_map.get(item.register_giftcard_id)
            item.user_rating = rating 

    return orders

@router.get("/admin/all", response_model=List[OrderSchema])
async def get_all_orders_admin(
    status: Optional[str] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    buyer_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(get_current_admin) 
):
    query = db.query(OrderORM).options(
        joinedload(OrderORM.items).joinedload(OrderItemORM.original_giftcard),
        joinedload(OrderORM.items).joinedload(OrderItemORM.enterprise),
        joinedload(OrderORM.items).joinedload(OrderItemORM.gift_items), # Carrega aqui também
        joinedload(OrderORM.owner)
    )
    
    if status:
        query = query.filter(OrderORM.status == status)
    if year:
        query = query.filter(extract('year', OrderORM.created_at) == year)
    if month:
        query = query.filter(extract('month', OrderORM.created_at) == month)
    if buyer_name:
        query = query.join(UserORM).filter(UserORM.username.ilike(f"%{buyer_name}%"))

    orders = query.order_by(OrderORM.created_at.desc()).all()

    return orders