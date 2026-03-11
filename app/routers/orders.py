from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal

from app.database import get_db
from app.models.models import (
    Order, OrderItem, Product, Coupon, Inventory, Shipping, Payment,
    OrderStatus, PaymentMethod, PaymentStatus, ShippingStatus, Customer
)
from app.routers.customers import get_current_customer
import uuid

router = APIRouter(prefix="/orders", tags=["Orders"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class OrderItemIn(BaseModel):
    product_id: int
    quantity:   int


class OrderCreate(BaseModel):
    items:            List[OrderItemIn]
    coupon_code:      Optional[str] = None
    payment_method:   PaymentMethod
    shipping_address: str
    shipping_city:    str
    shipping_state:   Optional[str] = None
    shipping_country: str = "Nigeria"
    shipping_postal:  Optional[str] = None
    notes:            Optional[str] = None


class OrderItemOut(BaseModel):
    product_id:  int
    quantity:    int
    unit_price:  float
    total_price: float
    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id:              int
    status:          str
    subtotal:        float
    discount_amount: float
    total:           float
    notes:           Optional[str]
    class Config:
        from_attributes = True


# ── Routes ────────────────────────────────────────────────────────────────────
@router.post("/", response_model=OrderOut, status_code=201)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current: Customer = Depends(get_current_customer),
):
    subtotal   = Decimal("0.00")
    items_data = []

    for item in data.items:
        product = db.query(Product).filter(
            Product.id == item.product_id, Product.is_active == True
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

        inv = db.query(Inventory).filter(Inventory.product_id == item.product_id).first()
        if not inv or inv.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for '{product.name}'")

        line_total = product.price * item.quantity
        subtotal  += line_total
        items_data.append((product, item.quantity, product.price, line_total))

    # Coupon
    discount = Decimal("0.00")
    coupon   = None
    if data.coupon_code:
        coupon = db.query(Coupon).filter(
            Coupon.code == data.coupon_code, Coupon.is_active == True
        ).first()
        if not coupon:
            raise HTTPException(status_code=400, detail="Invalid or expired coupon")
        if coupon.used_count >= coupon.max_uses:
            raise HTTPException(status_code=400, detail="Coupon has reached its usage limit")
        discount = subtotal * Decimal(str(coupon.discount_pct / 100))
        coupon.used_count += 1

    total = subtotal - discount

    # Create order
    order = Order(
        customer_id=current.id,
        coupon_id=coupon.id if coupon else None,
        subtotal=subtotal,
        discount_amount=discount,
        total=total,
        notes=data.notes,
    )
    db.add(order)
    db.flush()

    # Order items + deduct inventory
    for product, qty, unit_price, line_total in items_data:
        db.add(OrderItem(
            order_id=order.id, product_id=product.id,
            quantity=qty, unit_price=unit_price, total_price=line_total,
        ))
        inv = db.query(Inventory).filter(Inventory.product_id == product.id).first()
        inv.quantity -= qty

    # Payment (auto-complete for teaching purposes)
    db.add(Payment(
        order_id=order.id,
        method=data.payment_method,
        status=PaymentStatus.completed,
        amount=total,
        reference=str(uuid.uuid4()),
    ))

    # Shipping — store full address snapshot from order data (not customer.address)
    db.add(Shipping(
        order_id=order.id,
        address=data.shipping_address,
        city=data.shipping_city,
        state=data.shipping_state,
        country=data.shipping_country,
        postal_code=data.shipping_postal,
        status=ShippingStatus.not_shipped,
    ))

    db.commit()
    db.refresh(order)
    return order


@router.get("/my-orders", response_model=List[OrderOut])
def my_orders(
    db: Session = Depends(get_db),
    current: Customer = Depends(get_current_customer),
):
    return db.query(Order).filter(Order.customer_id == current.id).order_by(Order.created_at.desc()).all()


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current: Customer = Depends(get_current_customer),
):
    order = db.query(Order).filter(
        Order.id == order_id, Order.customer_id == current.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
