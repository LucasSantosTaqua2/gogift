from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks # <--- Importado BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from typing import List
import os

from app.database.db_config import get_db
from app.models.order_orm import OrderItemORM, OrderItemStatus, OrderORM, OrderGiftItemORM
from app.models.user_orm import UserORM
from app.models.giftcard_orm import RegisterGiftCardORM
from app.security import enterprise_required
from app.services.email_service import send_email_with_template # <--- Importado serviço de email

router = APIRouter(
    prefix="/validation",
    tags=["Validation"]
)

# Rota para buscar um código e ver seus detalhes (Comprador ou Presente)
@router.get("/{code}")
async def get_item_by_code(code: str, db: Session = Depends(get_db), current_user: UserORM = Depends(enterprise_required)):
    # 1. Tenta achar na lista do comprador (final_giftcard_codes)
    order_item = db.query(OrderItemORM).options(
        joinedload(OrderItemORM.order).joinedload(OrderORM.owner),
        joinedload(OrderItemORM.original_giftcard)
    ).filter(
        OrderItemORM.final_giftcard_codes.contains(code)
    ).first()

    # 2. Se não achou, tenta achar na lista de presentes (OrderGiftItemORM)
    if not order_item:
        gift_item = db.query(OrderGiftItemORM).options(
            joinedload(OrderGiftItemORM.order_item).joinedload(OrderItemORM.original_giftcard),
            joinedload(OrderGiftItemORM.order_item).joinedload(OrderItemORM.order).joinedload(OrderORM.owner)
        ).filter(
            OrderGiftItemORM.codes.contains(code)
        ).first()
        
        if gift_item:
            order_item = gift_item.order_item

    # Se não achou em lugar nenhum
    if not order_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código não encontrado ou já utilizado.")

    # Verifica se pertence à empresa logada
    if order_item.original_giftcard.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Este Gift Card não pertence à sua empresa.")

    return order_item

# Rota para marcar um código como utilizado
@router.put("/{code}/use")
async def mark_code_as_used(
    code: str, 
    background_tasks: BackgroundTasks, # <--- Injeção para envio assíncrono
    db: Session = Depends(get_db), 
    current_user: UserORM = Depends(enterprise_required)
):
    # --- BUSCA O CÓDIGO (Lógica Dupla) ---
    is_gift = False
    gift_item_found = None

    # 1. Busca no Comprador (Carregando owner para e-mail)
    order_item = db.query(OrderItemORM).options(
        joinedload(OrderItemORM.original_giftcard),
        joinedload(OrderItemORM.gift_items),
        joinedload(OrderItemORM.order).joinedload(OrderORM.owner) # Necessário para e-mail do comprador
    ).filter(
        OrderItemORM.final_giftcard_codes.contains(code)
    ).first()

    # 2. Busca no Presente
    if not order_item:
        gift_item_found = db.query(OrderGiftItemORM).options(
            joinedload(OrderGiftItemORM.order_item).joinedload(OrderItemORM.original_giftcard),
            joinedload(OrderGiftItemORM.order_item).joinedload(OrderItemORM.gift_items)
        ).filter(
            OrderGiftItemORM.codes.contains(code)
        ).first()

        if gift_item_found:
            order_item = gift_item_found.order_item
            is_gift = True

    # Validações iniciais
    if not order_item or order_item.original_giftcard.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código não encontrado ou inválido para esta empresa.")

    # --- LÓGICA DE BAIXA ---
    code = code.strip()
    success = False

    if is_gift and gift_item_found:
        # Lógica para Presente
        gift_codes = [c.strip() for c in (gift_item_found.codes or "").split(';') if c.strip()]
        if code in gift_codes:
            gift_codes.remove(code)
            gift_item_found.codes = ";".join(gift_codes)
            success = True
    else:
        # Lógica para Comprador
        available_codes = [c.strip() for c in (order_item.final_giftcard_codes or "").split(';') if c.strip()]
        if code in available_codes:
            available_codes.remove(code)
            order_item.final_giftcard_codes = ";".join(available_codes)
            success = True

    if success:
        # Adiciona aos usados do ITEM PAI
        used_codes = [c.strip() for c in (order_item.used_codes or "").split(';') if c.strip()]
        used_codes.append(code)
        order_item.used_codes = ";".join(used_codes)

        # --- ATUALIZA STATUS DO PEDIDO ---
        has_codes_left = False
        
        # 1. Sobrou do comprador?
        if order_item.final_giftcard_codes and order_item.final_giftcard_codes.strip():
            has_codes_left = True
        
        # 2. Sobrou de algum presente?
        if not has_codes_left and order_item.gift_items:
            for g in order_item.gift_items:
                if g.codes and g.codes.strip():
                    has_codes_left = True
                    break

        if not has_codes_left:
            order_item.status = OrderItemStatus.USED
        else:
            order_item.status = OrderItemStatus.PARTIALLY_USED
        
        db.commit()
        db.refresh(order_item)

        # --- ENVIO DE E-MAIL DE AVISO ---
        try:
            recipient_email = None
            recipient_name = None

            if is_gift and gift_item_found:
                recipient_email = gift_item_found.recipient_email
                recipient_name = gift_item_found.recipient_name
            else:
                # Se não é presente, o dono é o comprador
                recipient_email = order_item.order.owner.email
                recipient_name = order_item.order.owner.username

            if recipient_email:
                email_data = {
                    "recipient_name": recipient_name,
                    "product_title": order_item.original_giftcard.title,
                    "code": code,
                    "enterprise_name": current_user.username # Nome da empresa que validou
                }
                
                background_tasks.add_task(
                    send_email_with_template,
                    subject="Seu Gift Card foi utilizado! ✅",
                    recipients=[recipient_email],
                    template_name="gift_used.html",
                    template_body=email_data
                )
        except Exception as e:
            # Não queremos falhar a validação se o e-mail falhar, apenas logar
            print(f"Erro ao tentar enviar e-mail de uso: {e}")

        return order_item
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código já foi utilizado ou é inválido.")

# Rota para ver o histórico
@router.get("/history/me")
async def get_my_used_items(db: Session = Depends(get_db), current_user: UserORM = Depends(enterprise_required)):
    used_items = db.query(OrderItemORM).join(
        RegisterGiftCardORM, OrderItemORM.register_giftcard_id == RegisterGiftCardORM.id
    ).join(
        OrderORM, OrderItemORM.order_id == OrderORM.id
    ).options(
        joinedload(OrderItemORM.order).joinedload(OrderORM.owner),
        joinedload(OrderItemORM.original_giftcard)
    ).filter(
        RegisterGiftCardORM.user_id == current_user.id,
        OrderItemORM.status.in_([OrderItemStatus.USED, OrderItemStatus.PARTIALLY_USED])
    ).order_by(
        OrderORM.created_at.desc()
    ).all()
    
    return used_items