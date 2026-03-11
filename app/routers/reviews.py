from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.models.models import Review, Customer
from app.routers.customers import get_current_customer

router = APIRouter(prefix="/reviews", tags=["Reviews"])


class ReviewCreate(BaseModel):
    product_id: int
    rating: int
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    id: int
    product_id: int
    customer_id: int
    rating: int
    comment: Optional[str]

    class Config:
        from_attributes = True


@router.post("/", response_model=ReviewOut, status_code=201)
def create_review(data: ReviewCreate, db: Session = Depends(get_db), current: Customer = Depends(get_current_customer)):
    if not (1 <= data.rating <= 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    review = Review(product_id=data.product_id, customer_id=current.id, rating=data.rating, comment=data.comment)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/product/{product_id}", response_model=List[ReviewOut])
def product_reviews(product_id: int, db: Session = Depends(get_db)):
    return db.query(Review).filter(Review.product_id == product_id).all()
