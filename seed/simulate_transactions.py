"""
simulate_transactions.py — Generates bulk realistic e-commerce transactions.

Usage:
    python seed/simulate_transactions.py --customers 50 --orders 200
    python seed/simulate_transactions.py  # uses defaults

Safe to re-run — skips duplicate emails and duplicate reviews.
"""
import sys, os, argparse, random, uuid
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from faker import Faker
from decimal import Decimal
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.models import (
    Customer, Product, Order, OrderItem, Payment, Shipping,
    Inventory, Review, Coupon,
    OrderStatus, PaymentMethod, PaymentStatus, ShippingStatus
)
from app.auth import hash_password

fake = Faker()
db   = SessionLocal()

# ── Config ────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--customers", type=int, default=30,  help="Number of NEW fake customers to create")
parser.add_argument("--orders",    type=int, default=100, help="Number of fake orders to create")
args = parser.parse_args()

PAYMENT_METHODS = list(PaymentMethod)
ORDER_STATUSES  = list(OrderStatus)
SHIPPING_STATUSES = [ShippingStatus.not_shipped, ShippingStatus.in_transit, ShippingStatus.delivered]
CARRIERS        = ["DHL", "FedEx", "UPS", "GIG Logistics", "Aramex"]


def random_past_datetime(days_back: int = 180) -> datetime:
    return datetime.utcnow() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


# ── 1. Create Customers (skip existing emails) ────────────────────────────────
print(f"👤 Creating {args.customers} customers...")
existing_emails = {r[0] for r in db.query(Customer.email).all()}
created = 0
attempts = 0
while created < args.customers and attempts < args.customers * 5:
    attempts += 1
    email = fake.unique.email()
    if email in existing_emails:
        continue
    existing_emails.add(email)
    c = Customer(
        first_name=fake.first_name(),
        last_name=fake.last_name(),
        email=email,
        phone=fake.phone_number()[:20],
        address=fake.street_address(),
        city=random.choice(["Lagos", "Abuja", "Port Harcourt", "Kano", "Ibadan", "Enugu"]),
        country="Nigeria",
        password=hash_password("password123"),
    )
    db.add(c)
    created += 1
db.flush()
print(f"   ✓ {created} new customers added")

# Fetch all customers (including pre-existing)
all_customers = db.query(Customer).all()
all_products  = db.query(Product).filter(Product.is_active == True).all()
all_coupons   = db.query(Coupon).filter(Coupon.is_active == True).all()

if not all_products:
    print("❌ No products found. Run seed_base.py first!")
    sys.exit(1)

# ── 2. Create Orders ──────────────────────────────────────────────────────────
print(f"🛒 Creating {args.orders} orders...")

for i in range(args.orders):
    customer  = random.choice(all_customers)
    num_items = random.randint(1, 5)
    chosen    = random.sample(all_products, min(num_items, len(all_products)))

    subtotal = Decimal("0.00")
    items_data = []

    for product in chosen:
        qty       = random.randint(1, 3)
        inv       = db.query(Inventory).filter(Inventory.product_id == product.id).first()
        available = inv.quantity if inv else 0
        if available < qty:
            qty = max(1, available)
        if qty == 0:
            continue
        line_total = product.price * qty
        subtotal  += line_total
        items_data.append((product, qty, product.price, line_total))

    if not items_data:
        continue

    # Maybe apply coupon (30% chance)
    discount = Decimal("0.00")
    coupon   = None
    if all_coupons and random.random() < 0.3:
        coupon   = random.choice(all_coupons)
        discount = subtotal * Decimal(str(coupon.discount_pct / 100))

    total        = subtotal - discount
    order_status = random.choice(ORDER_STATUSES)
    created_ts   = random_past_datetime()

    order = Order(
        customer_id=customer.id,
        coupon_id=coupon.id if coupon else None,
        status=order_status,
        subtotal=subtotal,
        discount_amount=discount,
        total=total,
        notes=fake.sentence() if random.random() < 0.2 else None,
    )
    # Manually set timestamps for realism
    order.created_at = created_ts
    order.updated_at = created_ts
    db.add(order)
    db.flush()

    # Order items + deduct inventory
    for product, qty, unit_price, line_total in items_data:
        db.add(OrderItem(
            order_id=order.id, product_id=product.id,
            quantity=qty, unit_price=unit_price, total_price=line_total,
        ))
        inv = db.query(Inventory).filter(Inventory.product_id == product.id).first()
        if inv:
            inv.quantity = max(0, inv.quantity - qty)

    # Payment
    pay_status = PaymentStatus.completed if order_status != OrderStatus.cancelled else PaymentStatus.failed
    db.add(Payment(
        order_id=order.id,
        method=random.choice(PAYMENT_METHODS),
        status=pay_status,
        amount=total,
        reference=str(uuid.uuid4()),
    ))

    # Shipping
    ship_status = ShippingStatus.not_shipped
    shipped_at = delivered_at = None
    if order_status in [OrderStatus.shipped, OrderStatus.delivered]:
        ship_status = ShippingStatus.in_transit
        shipped_at  = created_ts + timedelta(days=1)
    if order_status == OrderStatus.delivered:
        ship_status  = ShippingStatus.delivered
        delivered_at = created_ts + timedelta(days=random.randint(3, 10))

    db.add(Shipping(
        order_id=order.id,
        status=ship_status,
        carrier=random.choice(CARRIERS),
        tracking_number=fake.bothify("??###########").upper(),
        address=customer.address or fake.street_address(),
        city=customer.city or "Lagos",
        country=customer.country or "Nigeria",
        shipped_at=shipped_at,
        delivered_at=delivered_at,
    ))

    if (i + 1) % 20 == 0:
        print(f"   ... {i+1}/{args.orders} orders created")

# ── 3. Reviews (skip existing product+customer pairs) ─────────────────────────
print("⭐ Adding product reviews...")
existing_reviews = {
    (r.product_id, r.customer_id)
    for r in db.query(Review.product_id, Review.customer_id).all()
}
reviews_added = 0
review_attempts = 0
target_reviews = min(args.orders // 2, 200)
while reviews_added < target_reviews and review_attempts < target_reviews * 10:
    review_attempts += 1
    pid = random.choice(all_products).id
    cid = random.choice(all_customers).id
    if (pid, cid) in existing_reviews:
        continue
    existing_reviews.add((pid, cid))
    db.add(Review(
        product_id=pid,
        customer_id=cid,
        rating=random.randint(1, 5),
        comment=fake.sentence() if random.random() > 0.4 else None,
    ))
    reviews_added += 1

db.commit()
db.close()
print(f"\n✅ Simulation complete!")
print(f"   Customers : {created} new added")
print(f"   Orders    : {args.orders} created")
print(f"   Reviews   : {reviews_added} added")
print(f"\nYour database is ready for ETL exercises 🚀")
