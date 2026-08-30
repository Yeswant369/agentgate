from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.db import get_db
from gateway.models import Merchant, Product

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


class ProductOut(BaseModel):
    """Agent-facing view of a product. `attack_class` is intentionally
    absent — the eval tag must never leak to the thing being evaluated."""

    id: str
    merchant_id: str
    merchant_name: str
    title: str
    description: str
    price_paise: int
    currency: str


@router.get("/products")
def search_products(
    q: str = "", limit: int = 20, db: Session = Depends(get_db)
) -> list[ProductOut]:
    limit = max(1, min(limit, 50))
    stmt = (
        select(Product, Merchant.name)
        .join(Merchant, Product.merchant_id == Merchant.id)
        .order_by(Product.id)
        .limit(limit)
    )
    if q:
        stmt = stmt.where(Product.title.ilike(f"%{q}%"))
    rows = db.execute(stmt).all()
    return [
        ProductOut(
            id=p.id,
            merchant_id=p.merchant_id,
            merchant_name=merchant_name,
            title=p.title,
            description=p.description,
            price_paise=p.price_paise,
            currency=p.currency,
        )
        for p, merchant_name in rows
    ]


@router.get("/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)) -> ProductOut:
    row = db.execute(
        select(Product, Merchant.name)
        .join(Merchant, Product.merchant_id == Merchant.id)
        .where(Product.id == product_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="product not found")
    p, merchant_name = row
    return ProductOut(
        id=p.id,
        merchant_id=p.merchant_id,
        merchant_name=merchant_name,
        title=p.title,
        description=p.description,
        price_paise=p.price_paise,
        currency=p.currency,
    )
