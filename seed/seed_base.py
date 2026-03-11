"""
seed_base.py — Run once to populate categories, products, inventory, and coupons.
Usage: python seed/seed_base.py
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.models import Category, Product, Inventory, Coupon
from decimal import Decimal

db = SessionLocal()

# ── Categories ────────────────────────────────────────────────────────────────
categories = [
    {"name": "Electronics",  "slug": "electronics"},
    {"name": "Clothing",     "slug": "clothing"},
    {"name": "Books",        "slug": "books"},
    {"name": "Home & Kitchen","slug": "home-kitchen"},
    {"name": "Sports",       "slug": "sports"},
]

cat_objects = {}
for c in categories:
    obj = db.query(Category).filter(Category.slug == c["slug"]).first()
    if not obj:
        obj = Category(**c)
        db.add(obj)
        db.flush()
    cat_objects[c["slug"]] = obj

# ── Products ──────────────────────────────────────────────────────────────────
products = [
    # Electronics
    {"name": "Samsung Galaxy A54",     "slug": "samsung-galaxy-a54",     "price": 299.99, "category": "electronics", "description": "Mid-range Android smartphone"},
    {"name": "Wireless Earbuds Pro",   "slug": "wireless-earbuds-pro",   "price": 49.99,  "category": "electronics", "description": "Noise-cancelling wireless earbuds"},
    {"name": "USB-C Hub 7-in-1",       "slug": "usb-c-hub-7in1",         "price": 35.00,  "category": "electronics", "description": "Multiport USB-C adapter"},
    {"name": "Mechanical Keyboard",    "slug": "mechanical-keyboard",    "price": 79.99,  "category": "electronics", "description": "TKL mechanical keyboard, red switches"},

    # Clothing
    {"name": "Classic White Tee",      "slug": "classic-white-tee",      "price": 15.99,  "category": "clothing",    "description": "100% cotton unisex t-shirt"},
    {"name": "Slim Fit Chinos",        "slug": "slim-fit-chinos",        "price": 39.99,  "category": "clothing",    "description": "Comfortable slim-fit chino trousers"},
    {"name": "Puffer Jacket",          "slug": "puffer-jacket",          "price": 89.99,  "category": "clothing",    "description": "Lightweight winter puffer jacket"},

    # Books
    {"name": "Python for Data Analysis","slug": "python-data-analysis",  "price": 42.00,  "category": "books",       "description": "Wes McKinney's pandas bible"},
    {"name": "Designing Data-Intensive Apps","slug": "ddia",             "price": 55.00,  "category": "books",       "description": "Martin Kleppmann's systems classic"},
    {"name": "The Pragmatic Programmer","slug": "pragmatic-programmer",  "price": 38.00,  "category": "books",       "description": "Hunt & Thomas — timeless software wisdom"},

    # Home & Kitchen
    {"name": "Stainless Steel Blender","slug": "stainless-blender",      "price": 65.00,  "category": "home-kitchen","description": "1200W high-speed blender"},
    {"name": "Air Fryer 4L",           "slug": "air-fryer-4l",           "price": 79.00,  "category": "home-kitchen","description": "Digital air fryer with 8 presets"},

    # Sports
    {"name": "Yoga Mat 6mm",           "slug": "yoga-mat-6mm",           "price": 22.99,  "category": "sports",      "description": "Non-slip eco-friendly yoga mat"},
    {"name": "Adjustable Dumbbells",   "slug": "adjustable-dumbbells",   "price": 119.99, "category": "sports",      "description": "5-25kg adjustable dumbbell pair"},
    {"name": "Running Shoes",          "slug": "running-shoes",          "price": 85.00,  "category": "sports",      "description": "Lightweight breathable running shoes"},
]

prod_objects = []
for p in products:
    cat = cat_objects[p.pop("category")]
    obj = db.query(Product).filter(Product.slug == p["slug"]).first()
    if not obj:
        obj = Product(**p, category_id=cat.id)
        db.add(obj)
        db.flush()
    prod_objects.append(obj)

# ── Inventory (always replenish to 500) ───────────────────────────────────────
for prod in prod_objects:
    inv = db.query(Inventory).filter(Inventory.product_id == prod.id).first()
    if inv:
        inv.quantity = 500
    else:
        db.add(Inventory(product_id=prod.id, quantity=500, reorder_lvl=20))

# ── Coupons ───────────────────────────────────────────────────────────────────
coupons = [
    {"code": "WELCOME10", "discount_pct": 10.0, "max_uses": 500},
    {"code": "SAVE20",    "discount_pct": 20.0, "max_uses": 100},
    {"code": "FLASH50",   "discount_pct": 50.0, "max_uses": 50},
]
for c in coupons:
    if not db.query(Coupon).filter(Coupon.code == c["code"]).first():
        db.add(Coupon(**c))

db.commit()
db.close()
print("✅ Base seed complete — categories, products, inventory, coupons loaded!")
