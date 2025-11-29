import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc, func, desc
from typing import List, Optional
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
from sqlalchemy.exc import IntegrityError
from PIL import Image, ImageOps
from nsfw_image_detector import NSFWDetector
from io import BytesIO

from app.database.db_config import get_db
from app.enums.sold_status import SoldStatus
from app.models.giftcard_orm import GiftCardReviewORM, RegisterGiftCardORM, SoldGiftCardORM
from app.models.giftcard_models import RegisterGiftCard, ReviewCreate, ReviewResponse, SoldGiftCardDetails
from app.models.order_orm import OrderItemORM, OrderORM, OrderStatus
from app.models.user_orm import UserORM
from app.security import get_current_user, enterprise_required

router = APIRouter(
    prefix="/giftcards",
    tags=["GiftCards"],
    responses={404: {"description": "Not found"}},
)

UPLOAD_DIRECTORY = "uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

nsfw_detector = NSFWDetector()

# --- DEFINIÇÃO DE TAXAS ---
PLATFORM_COMMISSION_PERCENTAGE = Decimal("0.03")

def calculate_selling_price(desired_amount: Decimal) -> Decimal:
    if desired_amount <= 0:
        return Decimal("0.00")

    selling_price = desired_amount * (Decimal("1.0") + PLATFORM_COMMISSION_PERCENTAGE)

    return selling_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def process_and_save_image(image_data: BytesIO, output_path: str):
    """
    Redimensiona, corta para 740x740, comprime e salva a imagem.
    """
    try:
        image_data.seek(0)
        img = Image.open(image_data)
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img_quadrada = ImageOps.fit(img, (740, 740), Image.Resampling.LANCZOS)
        
        img_quadrada.save(output_path, "JPEG", optimize=True, quality=85)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar a imagem: {e}"
        )

@router.post("/", response_model=RegisterGiftCard, status_code=status.HTTP_201_CREATED)
async def create_giftcard(
    title: str = Form(...),
    desired_amount: Decimal = Form(...),
    quantityavailable: int = Form(...),
    category_id: Optional[int] = Form(None),
    validade: Optional[date] = Form(None),
    ativo: bool = Form(True),
    description: Optional[str] = Form(None),
    generaterandomly: bool = Form(False),
    codes: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: UserORM = Depends(enterprise_required),
):
    try:
        selling_price = calculate_selling_price(desired_amount)
        if selling_price <= 0:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O valor desejado resulta em um preço de venda inválido após taxas.")
    except ValueError as e:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    image_url = None
    if image:
        image_bytes = await image.read()
        image_stream = BytesIO(image_bytes)

        try:
            pil_image = Image.open(image_stream)
            is_nsfw = nsfw_detector.is_nsfw(pil_image)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Arquivo de imagem inválido ou corrompido: {e}"
            )

        if is_nsfw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A imagem contém conteúdo impróprio e não pode ser enviada."
            )

        image_name = f"{uuid.uuid4()}.jpg"
        file_path = os.path.join(UPLOAD_DIRECTORY, image_name)

        process_and_save_image(image_stream, file_path)
        image_url = image_name

    db_giftcard = RegisterGiftCardORM(
        user_id=current_user.id,
        title=title,
        valor=selling_price, 
        desired_amount=desired_amount,
        validade=validade,
        ativo=ativo,
        description=description,
        quantityavailable=quantityavailable,
        generaterandomly=generaterandomly,
        codes=codes,
        imageUrl=image_url,
        category_id=category_id
    )
    db.add(db_giftcard)
    db.commit()
    db.refresh(db_giftcard)
    return db_giftcard

@router.put("/{giftcard_id}", response_model=RegisterGiftCard)
async def update_giftcard(
    giftcard_id: uuid.UUID,
    current_user: UserORM = Depends(enterprise_required),
    title: str = Form(...),
    desired_amount: Decimal = Form(...),
    quantityavailable: int = Form(...),
    category_id: Optional[int] = Form(None),
    validade: Optional[date] = Form(None),
    ativo: bool = Form(True),
    description: Optional[str] = Form(None),
    generaterandomly: bool = Form(False),
    codes: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    db_giftcard = db.query(RegisterGiftCardORM).options(
        joinedload(RegisterGiftCardORM.sold_cards)
    ).filter(RegisterGiftCardORM.id == giftcard_id).first()
    
    if db_giftcard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gift Card not found")
    if db_giftcard.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to perform this action")
    
    has_sales = len(db_giftcard.sold_cards) > 0
    
    if has_sales:
        if db_giftcard.title != title:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível alterar o Título de um produto que já possui vendas.")
        
        if db_giftcard.desired_amount != desired_amount:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível alterar o Valor de um produto que já possui vendas.")

    try:
        selling_price = calculate_selling_price(desired_amount)
        if selling_price <= 0:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O valor desejado resulta em um preço de venda inválido após taxas.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    image_url = db_giftcard.imageUrl
    if image:
        image_bytes = await image.read()
        image_stream = BytesIO(image_bytes)

        try:
            pil_image = Image.open(image_stream)
            is_nsfw = nsfw_detector.is_nsfw(pil_image)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Arquivo de imagem inválido ou corrompido: {e}"
            )
        
        if is_nsfw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A nova imagem contém conteúdo impróprio."
            )

        if image_url and os.path.exists(os.path.join(UPLOAD_DIRECTORY, image_url)):
            try:
                os.remove(os.path.join(UPLOAD_DIRECTORY, image_url))
            except Exception:
                pass 
    
        image_name = f"{uuid.uuid4()}.jpg"
        file_path = os.path.join(UPLOAD_DIRECTORY, image_name)
        process_and_save_image(image_stream, file_path)
        image_url = image_name
    
    db_giftcard.title = title
    db_giftcard.valor = selling_price
    db_giftcard.desired_amount = desired_amount
    db_giftcard.validade = validade
    db_giftcard.ativo = ativo
    db_giftcard.description = description
    db_giftcard.quantityavailable = quantityavailable
    db_giftcard.generaterandomly = generaterandomly
    db_giftcard.codes = codes
    db_giftcard.imageUrl = image_url
    db_giftcard.category_id = category_id

    db.commit()
    db.refresh(db_giftcard)
    return db_giftcard

@router.post("/{giftcard_id}/rate", response_model=ReviewResponse)
async def rate_gift_card(
    giftcard_id: uuid.UUID,
    review: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: UserORM = Depends(get_current_user)
):
    product = db.query(RegisterGiftCardORM).filter(RegisterGiftCardORM.id == giftcard_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    has_purchased = db.query(OrderItemORM).join(OrderORM).filter(
        OrderItemORM.register_giftcard_id == giftcard_id,
        OrderORM.owner_id == current_user.id,
        OrderORM.status == OrderStatus.APPROVED
    ).first()

    if not has_purchased:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Você só pode avaliar produtos que comprou e cujo pagamento foi aprovado."
        )

    existing_review = db.query(GiftCardReviewORM).filter(
        GiftCardReviewORM.giftcard_id == giftcard_id,
        GiftCardReviewORM.user_id == current_user.id
    ).first()

    if existing_review:
        existing_review.rating = review.rating
        existing_review.comment = review.comment
        existing_review.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_review)
        return ReviewResponse(
            id=existing_review.id, rating=existing_review.rating, 
            comment=existing_review.comment, created_at=existing_review.created_at, 
            user_name=current_user.username
        )

    new_review = GiftCardReviewORM(
        user_id=current_user.id,
        giftcard_id=giftcard_id,
        rating=review.rating,
        comment=review.comment
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    
    return ReviewResponse(
        id=new_review.id, rating=new_review.rating, 
        comment=new_review.comment, created_at=new_review.created_at, 
        user_name=current_user.username
    )

@router.get("/top-rated/", response_model=List[RegisterGiftCard])
def get_top_rated_giftcards(db: Session = Depends(get_db)):
    query = db.query(
        RegisterGiftCardORM,
        func.coalesce(func.avg(GiftCardReviewORM.rating), 0).label('avg_rating')
    ).outerjoin(GiftCardReviewORM).group_by(RegisterGiftCardORM.id)
    
    query = query.filter(RegisterGiftCardORM.ativo == True)
    
    query = query.order_by(desc('avg_rating'))
    
    results = query.limit(5).all() 
    
    giftcards = []
    for gc, avg in results:

        giftcards.append(gc)
        
    return giftcards

@router.get("/me", response_model=List[RegisterGiftCard])
def read_my_giftcards(current_user: UserORM = Depends(get_current_user), db: Session = Depends(get_db)):
     return db.query(RegisterGiftCardORM).options(
         joinedload(RegisterGiftCardORM.category),
         joinedload(RegisterGiftCardORM.sold_cards),
         joinedload(RegisterGiftCardORM.reviews)
     ).filter(RegisterGiftCardORM.user_id == current_user.id).all()

@router.get("/search/", response_model=List[RegisterGiftCard])
def search_giftcards(
    q: Optional[str] = None,
    category_id: Optional[int] = Query(None),
    min_price: Optional[Decimal] = Query(None),
    max_price: Optional[Decimal] = Query(None),
    sort_by: Optional[str] = Query(None), 
    db: Session = Depends(get_db)
):
    query = db.query(RegisterGiftCardORM).options(joinedload(RegisterGiftCardORM.category)).filter(RegisterGiftCardORM.ativo == True)
  
    if q:
        search_term = f"%{q}%"
        query = query.filter(RegisterGiftCardORM.title.ilike(search_term))
    
    if category_id:
        query = query.filter(RegisterGiftCardORM.category_id == category_id)

    if min_price is not None:
        query = query.filter(RegisterGiftCardORM.valor >= min_price)
    if max_price is not None:
        query = query.filter(RegisterGiftCardORM.valor <= max_price)

    if sort_by == "price_asc":
        query = query.order_by(asc(RegisterGiftCardORM.valor))
    elif sort_by == "price_desc":
        query = query.order_by(desc(RegisterGiftCardORM.valor))
    elif sort_by == "nota_desc":
        query = query.outerjoin(GiftCardReviewORM)\
                     .group_by(RegisterGiftCardORM.id)\
                     .order_by(desc(func.avg(GiftCardReviewORM.rating)))
    
    return query.all()

@router.get("/category/{category_id}", response_model=List[RegisterGiftCard])
def get_giftcards_by_category(category_id: int, db: Session = Depends(get_db)):
    giftcards = db.query(RegisterGiftCardORM).options(joinedload(RegisterGiftCardORM.category)).filter(RegisterGiftCardORM.category_id == category_id, RegisterGiftCardORM.ativo == True).all()
    return giftcards


@router.get("/", response_model=List[RegisterGiftCard])
def read_all_giftcards(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    giftcards = db.query(RegisterGiftCardORM).options(joinedload(RegisterGiftCardORM.category)).filter(RegisterGiftCardORM.ativo == True).offset(skip).limit(limit).all()

    return giftcards

@router.get("/best-sellers", response_model=List[RegisterGiftCard])
def get_best_sellers(db: Session = Depends(get_db)):
    # Busca os top 5 produtos mais vendidos (soma da quantidade em pedidos APROVADOS)
    best_sellers_query = db.query(RegisterGiftCardORM)\
        .join(OrderItemORM, RegisterGiftCardORM.id == OrderItemORM.register_giftcard_id)\
        .join(OrderORM, OrderItemORM.order_id == OrderORM.id)\
        .filter(
            OrderORM.status == OrderStatus.APPROVED,
            RegisterGiftCardORM.ativo == True
        )\
        .group_by(RegisterGiftCardORM.id)\
        .order_by(desc(func.sum(OrderItemORM.quantity)))\
        .limit(5)
        
    best_sellers = best_sellers_query.all()

    if len(best_sellers) < 5:
        needed = 5 - len(best_sellers)
        existing_ids = [p.id for p in best_sellers]
        
        random_fill = db.query(RegisterGiftCardORM)\
            .filter(
                RegisterGiftCardORM.ativo == True,
                RegisterGiftCardORM.id.notin_(existing_ids)
            )\
            .order_by(func.rand())\
            .limit(needed)\
            .all()
            
        best_sellers.extend(random_fill)
        
    return best_sellers

@router.get("/{giftcard_id}", response_model=RegisterGiftCard)
def read_giftcard_by_id(giftcard_id: uuid.UUID, db: Session = Depends(get_db)):
    db_giftcard = db.query(RegisterGiftCardORM).options(
        joinedload(RegisterGiftCardORM.category),
        joinedload(RegisterGiftCardORM.sold_cards),
        joinedload(RegisterGiftCardORM.reviews)
    ).filter(RegisterGiftCardORM.id == giftcard_id).first()
    
    if db_giftcard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gift Card not found")
    return db_giftcard

@router.delete("/{giftcard_id}", response_model=RegisterGiftCard)
def delete_giftcard(
    giftcard_id: uuid.UUID, 
    current_user: dict = Depends(enterprise_required),
    db: Session = Depends(get_db)
):
    db_giftcard = db.query(RegisterGiftCardORM).options(
        joinedload(RegisterGiftCardORM.sold_cards),
        joinedload(RegisterGiftCardORM.category),
        joinedload(RegisterGiftCardORM.reviews)
    ).filter(RegisterGiftCardORM.id == giftcard_id).first()
    
    if db_giftcard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gift Card not found")
        
    if db_giftcard.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to perform this action")

    if len(db_giftcard.sold_cards) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="Este Gift Card possui vendas registradas e não pode ser excluído."
        )
    
    response_data = RegisterGiftCard.model_validate(db_giftcard)
    
    image_to_remove = None
    if db_giftcard.imageUrl:
        image_path = os.path.join(UPLOAD_DIRECTORY, db_giftcard.imageUrl)
        if os.path.exists(image_path):
            image_to_remove = image_path

    try:
        db.delete(db_giftcard)
        db.commit()

        if image_to_remove:
            try:
                os.remove(image_to_remove)
            except Exception as e:
                print(f"Erro ao apagar imagem {image_to_remove}: {e}")
                pass

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="Este produto está vinculado a pedidos existentes e não pode ser excluído."
        )

    return response_data

@router.get("/codes/{giftcard_id}", response_model=List[str])
def get_giftcard_codes(giftcard_id: uuid.UUID, db: Session = Depends(get_db)):
    db_giftcard = db.query(RegisterGiftCardORM).filter(RegisterGiftCardORM.id == giftcard_id).first()
    if db_giftcard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gift Card not found")
    if not db_giftcard.codes:
        return []
    
    return db_giftcard.codes.split(';')


@router.get("/validate/{code}", response_model=SoldGiftCardDetails)
def validate_giftcard_code(code: str, db: Session = Depends(get_db), current_user: UserORM = Depends(enterprise_required)):
    sold_giftcard = db.query(SoldGiftCardORM)\
        .options(joinedload(SoldGiftCardORM.owner), joinedload(SoldGiftCardORM.original_giftcard))\
        .filter(SoldGiftCardORM.code == code).first()

    if not sold_giftcard:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gift Card não encontrado.")

    if sold_giftcard.original_giftcard.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Este Gift Card não pertence à sua empresa.")

    return SoldGiftCardDetails(
        id=sold_giftcard.id,
        code=sold_giftcard.code,
        status=sold_giftcard.status,
        purchase_date=sold_giftcard.purchase_date,
        register_giftcard_id=sold_giftcard.register_giftcard_id,
        owner_id=sold_giftcard.owner_id,
        owner_name=sold_giftcard.owner.username,
        original_giftcard=sold_giftcard.original_giftcard
    )

# ROTA VALIDAÇÃO
@router.put("/validate/{code}/use", response_model=SoldGiftCardDetails)
def mark_giftcard_as_used(code: str, db: Session = Depends(get_db), current_user: UserORM = Depends(enterprise_required)):
    sold_giftcard = db.query(SoldGiftCardORM)\
        .options(joinedload(SoldGiftCardORM.owner), joinedload(SoldGiftCardORM.original_giftcard))\
        .filter(SoldGiftCardORM.code == code).first()

    if not sold_giftcard:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gift Card não encontrado.")

    if sold_giftcard.original_giftcard.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Este Gift Card não pertence à sua empresa.")
    
    if sold_giftcard.status == SoldStatus.USED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Este Gift Card já foi utilizado.")

    sold_giftcard.status = SoldStatus.USED
    db.commit()
    db.refresh(sold_giftcard)

    return SoldGiftCardDetails(
        id=sold_giftcard.id,
        code=sold_giftcard.code,
        status=sold_giftcard.status,
        purchase_date=sold_giftcard.purchase_date,
        register_giftcard_id=sold_giftcard.register_giftcard_id,
        owner_id=sold_giftcard.owner_id,
        owner_name=sold_giftcard.owner.username,
        original_giftcard=sold_giftcard.original_giftcard
    )
    
# ROTA PARA HISTÓRICO
@router.get("/used/me", response_model=List[SoldGiftCardDetails])
def get_my_used_giftcards(db: Session = Depends(get_db), current_user: UserORM = Depends(enterprise_required)):
    used_giftcards = db.query(SoldGiftCardORM)\
        .join(RegisterGiftCardORM)\
        .options(joinedload(SoldGiftCardORM.owner), joinedload(SoldGiftCardORM.original_giftcard))\
        .filter(RegisterGiftCardORM.user_id == current_user.id)\
        .filter(SoldGiftCardORM.status == SoldStatus.USED)\
        .order_by(desc(SoldGiftCardORM.purchase_date))\
        .all()

    return [
        SoldGiftCardDetails(
            id=gc.id,
            code=gc.code,
            status=gc.status,
            purchase_date=gc.purchase_date,
            register_giftcard_id=gc.register_giftcard_id,
            owner_id=gc.owner_id,
            owner_name=gc.owner.username,
            original_giftcard=gc.original_giftcard
        ) for gc in used_giftcards
    ]

