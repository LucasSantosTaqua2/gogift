import mercadopago
import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from app.database.db_config import get_db
from app.models.giftcard_orm import RegisterGiftCardORM
from app.models.user_orm import UserORM
from app.security import get_current_user
from app.services.email_service import send_email_with_template
from app.models.order_orm import OrderORM, OrderItemORM, OrderStatus, OrderGiftItemORM
from app.services.order_cleanup_service import process_successful_order

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

router = APIRouter(
    prefix="/mercadopago",
    tags=["MercadoPago"],
)

access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
if not access_token:
    logging.error("Variável de ambiente MERCADOPAGO_ACCESS_TOKEN não foi definida!")
    raise RuntimeError("MERCADOPAGO_ACCESS_TOKEN não configurada.")
sdk = mercadopago.SDK(access_token)

# --- SCHEMAS ATUALIZADOS PARA PRESENTES ---
class GiftRecipient(BaseModel):
    name: str
    email: EmailStr
    quantity: int
    message: Optional[str] = None

class CartItem(BaseModel):
    product_id: uuid.UUID
    quantity: int
    # Lista opcional de presentes. Se vazio, tudo vai para o comprador.
    gifts: List[GiftRecipient] = Field(default_factory=list) 

class CartCheckout(BaseModel):
    items: List[CartItem]

# --- FUNÇÕES DE AUXÍLIO DE E-MAIL (Mantidas para uso local ou fallback) ---
def send_payment_pending_email(background_tasks: BackgroundTasks, order: OrderORM, items_details: List[dict]):
    email_body = {
        "username": order.owner.username,
        "order_id": str(order.id),
        "items": items_details,
        "total_price": float(order.total_amount)
    }
    background_tasks.add_task(
        send_email_with_template,
        subject="Seu Pedido na GoGift está Aguardando Pagamento",
        recipients=[order.owner.email],
        template_name="purchase_pending.html",
        template_body=email_body
    )

def send_purchase_confirmation_email(background_tasks: BackgroundTasks, order: OrderORM):
    base_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
    items_details = [
        {
            "title": item.original_giftcard.title,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "subtotal": float(item.unit_price * item.quantity),
            "final_giftcard_codes": item.final_giftcard_codes
        } for item in order.items
    ]

    email_body = {
        "username": order.owner.username,
        "order_id": str(order.id),
        "items": items_details,
        "total_price": float(order.total_amount),
        "base_url": base_url
    }

    background_tasks.add_task(
        send_email_with_template,
        subject="Sua Compra na GoGift foi Confirmada!",
        recipients=[order.owner.email],
        template_name="purchase_confirmation.html",
        template_body=email_body
    )

def send_payment_rejected_email(background_tasks: BackgroundTasks, order: OrderORM, reason: str):
    email_body = {
        "username": order.owner.username,
        "order_id": str(order.id).split('-')[0],
        "transaction_id": order.mercadopago_transaction_id or "N/A",
        "rejection_reason": reason
    }
    background_tasks.add_task(
        send_email_with_template,
        subject="Seu Pagamento foi Recusado - GoGift",
        recipients=[order.owner.email],
        template_name="payment_rejected.html",
        template_body=email_body
    )

# --- ROTA DE CRIAÇÃO DE PREFERÊNCIA (CHECKOUT) ---
@router.post("/create_preference_cart", status_code=status.HTTP_201_CREATED)
async def create_preference_cart(
    cart: CartCheckout,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserORM = Depends(get_current_user)
):
    if not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O carrinho não pode estar vazio.")

    items_subtotal = Decimal("0.0")
    order_items_to_create = [] 
    items_for_email = []
    preference_items = []

    try:
        for item in cart.items:
            # --- VALIDAÇÃO DE PRESENTES ---
            total_gifts_qty = sum(g.quantity for g in item.gifts)
            if total_gifts_qty > item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"A quantidade de presentes ({total_gifts_qty}) excede a quantidade total do item ({item.quantity})."
                )
            # ------------------------------

            db_giftcard = db.query(RegisterGiftCardORM).options(
                joinedload(RegisterGiftCardORM.user).joinedload(UserORM.enterprise_details)
            ).filter(RegisterGiftCardORM.id == item.product_id).with_for_update().first()

            if not db_giftcard:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Gift Card com ID {item.product_id} não encontrado.")

            if not db_giftcard.user or not db_giftcard.user.enterprise_details:
                logging.error(f"Giftcard {db_giftcard.id} não possui uma empresa associada.")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este item não pode ser vendido.")

            if not db_giftcard.ativo:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Gift Card com ID {item.product_id} não está disponível.")
            
            if db_giftcard.quantityavailable < item.quantity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estoque insuficiente para '{db_giftcard.title}'.")

            item_selling_price = db_giftcard.valor 
            item_total = item_selling_price * item.quantity
            items_subtotal += item_total

            preference_items.append({
                "title": db_giftcard.title,
                "quantity": item.quantity,
                "unit_price": float(item_selling_price),
                "currency_id": "BRL"
            })
            
            items_for_email.append({
                "title": db_giftcard.title,
                "quantity": item.quantity,
                "subtotal": float(item_total)
            })

            item_enterprise_id = db_giftcard.user.enterprise_details.id
            item_desired_amount = db_giftcard.desired_amount
            
            # Prepara dados do item para criação posterior (Agrupado)
            order_items_to_create.append({
                "giftcard_id": db_giftcard.id,
                "enterprise_id": item_enterprise_id,
                "quantity": item.quantity, # Quantidade total
                "unit_price": item_selling_price,
                "seller_amount": item_desired_amount,
                "giftcard_instance": db_giftcard,
                "gifts": item.gifts # Lista de presentes para salvar
            })

        service_fee = items_subtotal * Decimal("0.05")
        
        preference_items.append({
            "title": "Taxa de Processamento (5%)",
            "quantity": 1,
            "unit_price": float(service_fee),
            "currency_id": "BRL"
        })
        
        final_total_amount = items_subtotal + service_fee

        new_order = OrderORM(
            owner_id=current_user.id,
            total_amount=final_total_amount,
            status=OrderStatus.PENDING
        )
        db.add(new_order)
        db.flush() # Gera ID do pedido
        new_order.owner = current_user

        giftcards_stock_to_update = {} 

        if order_items_to_create:
            for item_data in order_items_to_create:
                # 1. Cria o Item do Pedido
                new_order_item = OrderItemORM(
                    order_id=new_order.id,
                    register_giftcard_id=item_data["giftcard_id"],
                    enterprise_id=item_data["enterprise_id"],
                    quantity=item_data["quantity"],
                    unit_price=item_data["unit_price"],
                    seller_amount=item_data["seller_amount"]
                )
                db.add(new_order_item)
                db.flush() # Gera ID do item para relacionar os presentes

                # 2. Salva os Presentes vinculados a este item
                for gift in item_data["gifts"]:
                    new_gift_entry = OrderGiftItemORM(
                        order_item_id=new_order_item.id,
                        recipient_name=gift.name,
                        recipient_email=gift.email,
                        quantity=gift.quantity,
                        message=gift.message
                    )
                    db.add(new_gift_entry)

                # Contabiliza estoque para baixa
                gc_id = item_data["giftcard_id"]
                giftcards_stock_to_update[gc_id] = giftcards_stock_to_update.get(gc_id, 0) + item_data["quantity"]

            # Atualiza estoque no banco
            for gc_id, qty_reduce in giftcards_stock_to_update.items():
                 giftcard_instance = next((item["giftcard_instance"] for item in order_items_to_create if item["giftcard_id"] == gc_id), None)
                 if giftcard_instance:
                     current_quantity = db.query(RegisterGiftCardORM.quantityavailable).filter(RegisterGiftCardORM.id == gc_id).scalar()
                     if current_quantity is not None and current_quantity >= qty_reduce:
                         giftcard_instance.quantityavailable = current_quantity - qty_reduce
                     else:
                         db.rollback()
                         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Erro de concorrência no estoque para '{giftcard_instance.title}'. Tente novamente.")
                 else:
                     db.query(RegisterGiftCardORM).filter(RegisterGiftCardORM.id == gc_id).update({"quantityavailable": RegisterGiftCardORM.quantityavailable - qty_reduce}, synchronize_session=False)

        send_payment_pending_email(background_tasks, new_order, items_for_email)

        base_url = os.getenv("FRONTEND_URL", "http://localhost:4200")
        expiration_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        expiration_time_iso = expiration_time.isoformat("T", "milliseconds").replace('+00:00', 'Z')

        preference_data = {
            "items": preference_items,
            "back_urls": {"success": f"{base_url}/profile?status=approved", "failure": f"{base_url}/cart", "pending": f"{base_url}/profile"},
            "auto_return": "approved",
            "external_reference": str(new_order.id),
            "notification_url": f"{os.getenv('BACKEND_PUBLIC_URL')}/api/mercadopago/webhook",
            "expires": True,
            "date_of_expiration": expiration_time_iso,
            "payment_methods": {
                "excluded_payment_types": [
                    { "id": "ticket" } 
                ]
            }
        }

        preference_response = sdk.preference().create(preference_data)
        if not (preference_response and preference_response.get("status") in [200, 201]):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao criar preferência de pagamento.")

        new_order.mercadopago_transaction_id = preference_response["response"].get("id")
        db.commit()

        return {"preference_id": preference_response["response"]["id"], "init_point": preference_response["response"]["init_point"]}

    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        logging.critical(f"Erro ao criar preferência: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao processar o pedido.")


# --- WEBHOOK ---
@router.post("/webhook")
async def mercadopago_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body = await request.json()
    if body.get("type") != "payment":
        return Response(status_code=status.HTTP_200_OK)

    payment_id = body.get("data", {}).get("id")
    if not payment_id:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    try:
        payment_info_response = sdk.payment().get(payment_id)
        if not payment_info_response or payment_info_response.get("status") not in [200, 201]:
            logging.error(f"Não foi possível obter informações do Payment ID {payment_id}.")
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        payment_info = payment_info_response["response"]
        order_id_str = payment_info.get("external_reference")
        payment_status = payment_info.get("status")

        # Carrega pedido com todas as relações necessárias, incluindo os presentes
        order = db.query(OrderORM).options(
            joinedload(OrderORM.items).joinedload(OrderItemORM.original_giftcard),
            joinedload(OrderORM.items).joinedload(OrderItemORM.gift_items), # Carrega os presentes
            joinedload(OrderORM.owner)
        ).filter(OrderORM.id == order_id_str).first()

        if not order or order.status != OrderStatus.PENDING:
            logging.warning(f"Pedido {order_id_str} não encontrado ou já processado.")
            return Response(status_code=status.HTTP_200_OK)

        order.mercadopago_transaction_id = str(payment_info.get("id"))

        if payment_status == "approved":
            # --- CHAMA A LÓGICA CENTRALIZADA DE PROCESSAMENTO E DISTRIBUIÇÃO ---
            await process_successful_order(db, order, payment_info, background_tasks)
            
            # Envia confirmação para o comprador (com o que sobrou para ele)
            send_purchase_confirmation_email(background_tasks, order)

        elif payment_status in ["rejected", "cancelled", "refunded", "charged_back"]:
            original_status = order.status
            order.status = OrderStatus.REJECTED if payment_status not in ["refunded", "charged_back"] else OrderStatus.REFUNDED
            order.net_amount = None

            if original_status == OrderStatus.PENDING:
                # Devolve estoque
                giftcards_stock_to_return = {}
                for item in order.items:
                    gc_id = item.register_giftcard_id
                    giftcards_stock_to_return[gc_id] = giftcards_stock_to_return.get(gc_id, 0) + item.quantity

                for gc_id, qty_return in giftcards_stock_to_return.items():
                    db.query(RegisterGiftCardORM).filter(RegisterGiftCardORM.id == gc_id).update(
                        {"quantityavailable": RegisterGiftCardORM.quantityavailable + qty_return},
                        synchronize_session='fetch'
                    )

            rejection_reason = payment_info.get("status_detail", "Motivo não especificado.")
            if order.status == OrderStatus.REJECTED:
                 send_payment_rejected_email(background_tasks, order, rejection_reason)

        db.commit()

    except Exception as e:
        db.rollback()
        logging.critical(f"Erro CRÍTICO no webhook para payment_id {payment_id}: {e}", exc_info=True)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(status_code=status.HTTP_200_OK)