import logging
import copy  # <--- Faltava esta importação
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
import mercadopago
import os
import uuid
from decimal import Decimal

from app.database.db_config import SessionLocal, now_brt
from app.models.order_orm import OrderORM, OrderStatus, OrderItemORM, OrderGiftItemORM
from app.models.giftcard_orm import RegisterGiftCardORM
from app.services.email_service import send_email_with_template

# Configuração do Logging e do SDK do Mercado Pago
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

access_token = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
if not access_token:
    raise RuntimeError("MERCADOPAGO_ACCESS_TOKEN não configurada para o scheduler.")
sdk = mercadopago.SDK(access_token)


ORDER_EXPIRATION_MINUTES = 5

async def send_order_expired_email(order: OrderORM):
    """Prepara e envia o e-mail de pedido expirado."""
    email_body = {
        "username": order.owner.username, 
        "order_id": str(order.id).split('-')[0]
    }
    await send_email_with_template(
        subject="Seu Pedido na GoGift Expirou",
        recipients=[order.owner.email],
        template_name="order_expired.html",
        template_body=email_body
    )

async def process_successful_order(db: Session, order: OrderORM, payment_info: dict, background_tasks=None):
    """
    Processa um pedido aprovado: gera/reserva códigos, distribui entre presentes
    e envia os e-mails correspondentes.
    """
    logger.info(f"Processando pedido {order.id} como APROVADO.")
    
    # 1. Atualiza valor líquido se disponível (Lógica do Mercado Pago)
    net_received_amount = None
    if payment_info.get("transaction_details"):
        net_raw = payment_info.get("transaction_details", {}).get("net_received_amount")
        if net_raw is not None:
            try:
                net_received_amount = Decimal(str(net_raw))
            except Exception:
                logger.warning(f"Não foi possível converter net_received_amount '{net_raw}' para Decimal.")
    order.net_amount = net_received_amount
    order.status = OrderStatus.APPROVED

    # 2. Processa cada item do pedido
    for item in order.items:
        giftcard = item.original_giftcard
        assigned_codes = []

        # --- A. GERAÇÃO OU SELEÇÃO DOS CÓDIGOS (Para a quantidade TOTAL) ---
        if giftcard.generaterandomly:
            for _ in range(item.quantity):
                while True:
                    new_code = str(uuid.uuid4())
                    # Verifica duplicidade global simples (pode ser otimizado)
                    exists = db.query(OrderItemORM.id).filter(OrderItemORM.final_giftcard_codes.like(f"%{new_code}%")).first()
                    if not exists and new_code not in assigned_codes:
                        assigned_codes.append(new_code)
                        break
        else:
            # Lógica para códigos pré-definidos (estoque fixo)
            all_codes = {code.strip() for code in (giftcard.codes or "").split(';') if code.strip()}
            
            # Busca códigos já vendidos
            sold_codes_query = db.query(OrderItemORM.final_giftcard_codes).join(OrderORM).filter(
                OrderItemORM.register_giftcard_id == giftcard.id,
                OrderORM.status == OrderStatus.APPROVED
            ).all()
            sold_codes = {c.strip() for codes, in sold_codes_query if codes for c in codes.split(';')}
            
            available_codes = list(all_codes - sold_codes)
            
            if len(available_codes) < item.quantity:
                logger.error(f"Overbooking crítico no pedido {order.id} item {giftcard.id}!")
                # Pega o que tem disponível para não quebrar totalmente
                assigned_codes = available_codes[:item.quantity] 
            else:
                assigned_codes = available_codes[:item.quantity]

        # --- B. DISTRIBUIÇÃO DOS CÓDIGOS ---
        
        codes_pool = copy.deepcopy(assigned_codes) # Lista de códigos para distribuir
        
        # 1. Distribui para os Presenteados (OrderGiftItemORM)
        # Verifica se 'gift_items' foi carregado ou existe no objeto
        if hasattr(item, 'gift_items'):
            for gift_item in item.gift_items:
                qty_needed = gift_item.quantity
                
                # Pega a quantidade necessária do pool
                gift_codes = codes_pool[:qty_needed]
                # Remove do pool
                codes_pool = codes_pool[qty_needed:]
                
                # Salva no banco para o amigo
                gift_item.codes = ";".join(gift_codes)
                
                # Envia E-mail para o Presenteado
                if background_tasks:
                    email_data = {
                        "recipient_name": gift_item.recipient_name,
                        "sender_name": order.owner.username,
                        "product_title": giftcard.title,
                        "message": gift_item.message,
                        "codes": gift_codes,
                        "image_url": f"{os.getenv('BACKEND_PUBLIC_URL')}/uploads/{giftcard.imageUrl}" if giftcard.imageUrl else None
                    }
                    background_tasks.add_task(
                        send_email_with_template,
                        subject=f"Você ganhou um presente de {order.owner.username}!",
                        recipients=[gift_item.recipient_email],
                        template_name="gift_received.html", 
                        template_body=email_data
                    )

        # 2. O que sobrou vai para o Comprador
        item.final_giftcard_codes = ";".join(codes_pool)

async def cancel_expired_pending_orders():
    """
    Verifica pedidos pendentes, consulta o status no Mercado Pago e cancela se necessário.
    """
    db: Session = SessionLocal()
    try:
        logger.info("Scheduler: Iniciando verificação de pedidos pendentes expirados...")

        expiration_time = now_brt() - timedelta(minutes=ORDER_EXPIRATION_MINUTES)
        
        expired_orders = db.query(OrderORM).options(
            joinedload(OrderORM.items).joinedload(OrderItemORM.original_giftcard),
            joinedload(OrderORM.items).joinedload(OrderItemORM.gift_items), # Carregar presentes também
            joinedload(OrderORM.owner)
        ).filter(
            OrderORM.status == OrderStatus.PENDING,
            OrderORM.created_at < expiration_time
        ).all()

        if not expired_orders:
            logger.info("Scheduler: Nenhum pedido expirado encontrado.")
            return

        for order in expired_orders:
            payment_id = order.mercadopago_transaction_id
            final_status = None
            payment_info_response = None

            # 1. CONSULTAR O MERCADO PAGO PRIMEIRO
            if payment_id and not payment_id.startswith("pref_"): 
                try:
                    payment_info_response = sdk.payment().get(payment_id)
                    if payment_info_response and payment_info_response["status"] == 200:
                        final_status = payment_info_response["response"].get("status")
                except Exception as e:
                    logger.error(f"Scheduler: Falha ao consultar o payment_id {payment_id} no Mercado Pago: {e}")

            # 2. DECIDIR A AÇÃO COM BASE NO STATUS
            if final_status == 'approved':
                if payment_info_response and payment_info_response.get("response"):
                    payment_info = payment_info_response["response"]
                    # Background tasks não está disponível no scheduler cron, então enviamos síncrono ou adaptamos
                    # Aqui passamos None para background_tasks, o que impede envio de email dentro da função
                    # (Idealmente você injetaria um serviço de email síncrono aqui se crítico)
                    await process_successful_order(db, order, payment_info, background_tasks=None)
                else:
                    logger.error(f"Scheduler: Status 'approved' para {order.id} mas payment_info estava indisponível.")
            else:
                logger.warning(f"Scheduler: Pedido {order.id} expirou (Status MP: {final_status}). Cancelando e retornando estoque.")
                
                for item in order.items:
                    if item.original_giftcard:
                        item.original_giftcard.quantityavailable += item.quantity
                
                order.status = OrderStatus.EXPIRED
                
                await send_order_expired_email(order)
        
        db.commit()
        if expired_orders:
            logger.info(f"Scheduler: {len(expired_orders)} pedido(s) expirado(s) foram processados.")

    except Exception as e:
        logger.error(f"Scheduler: Erro CRÍTICO ao processar pedidos expirados: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()