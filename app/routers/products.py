from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.models.models import Product, Category, Inventory

router = APIRouter(prefix="/products", tags=["Products"])


class ProductOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    price: float
    image_url: Optional[str]
    is_active: bool
    category_id: Optional[int]
    inventory_qty: int = 0

    class Config:
        from_attributes = True


def _attach_inventory(product: Product, db: Session) -> ProductOut:
    inv = db.query(Inventory).filter(Inventory.product_id == product.id).first()
    data = ProductOut.model_validate(product)
    data.inventory_qty = inv.quantity if inv else 0
    return data


@router.get("/", response_model=List[ProductOut])
def list_products(skip: int = 0, limit: int = 50, category_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Product).join(Inventory, Inventory.product_id == Product.id)\
        .filter(Product.is_active == True, Inventory.quantity > 0)
    if category_id:
        q = q.filter(Product.category_id == category_id)
    return [_attach_inventory(p, db) for p in q.offset(skip).limit(limit).all()]


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _attach_inventory(product, db)


@router.get("/categories/all")
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()
