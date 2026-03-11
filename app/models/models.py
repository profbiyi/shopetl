from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, Enum, Numeric, UniqueConstraint,
    CheckConstraint, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


# ── Enums ──────────────────────────────────────────────────────────────────────

class OrderStatus(str, enum.Enum):
    pending    = "pending"
    processing = "processing"
    shipped    = "shipped"
    delivered  = "delivered"
    cancelled  = "cancelled"


class PaymentStatus(str, enum.Enum):
    pending   = "pending"
    completed = "completed"
    failed    = "failed"
    refunded  = "refunded"


class PaymentMethod(str, enum.Enum):
    card          = "card"
    paypal        = "paypal"
    bank_transfer = "bank_transfer"


class ShippingStatus(str, enum.Enum):
    not_shipped = "not_shipped"
    in_transit  = "in_transit"
    delivered   = "delivered"
    returned    = "returned"


# ── 1. categories ──────────────────────────────────────────────────────────────
#   Parent of products (one-to-many).
#   Soft-delete via is_active rather than hard delete to preserve product history.
# ───────────────────────────────────────────────────────────────────────────────
class Category(Base):
    __tablename__ = "categories"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(100), unique=True, nullable=False)
    slug       = Column(String(100), unique=True, nullable=False)
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship → products
    # passive_deletes: DB enforces ON DELETE RESTRICT (can't delete category
    # that still has products)
    products = relationship(
        "Product",
        back_populates="category",
        passive_deletes=True,
    )


# ── 2. products ────────────────────────────────────────────────────────────────
#   Belongs to one category (nullable FK → allows uncategorised products).
#   Has exactly one inventory row (one-to-one, enforced by UniqueConstraint
#   on inventory.product_id).
#   Has many order_items and reviews.
# ───────────────────────────────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="RESTRICT"),   # can't delete category with products
        nullable=True,
        index=True,
    )
    name        = Column(String(200), nullable=False)
    slug        = Column(String(200), unique=True, nullable=False)
    description = Column(Text)
    price       = Column(Numeric(10, 2), nullable=False)
    image_url   = Column(String(500))
    is_active   = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    category  = relationship("Category", back_populates="products")

    # One-to-one: every product must have exactly one inventory row
    inventory = relationship(
        "Inventory",
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",   # deleting product removes its inventory row
    )

    # One-to-many: a product can appear in many order lines
    # passive_deletes=True: we never hard-delete products that have been ordered
    order_items = relationship(
        "OrderItem",
        back_populates="product",
        passive_deletes=True,
    )

    # One-to-many: cascade delete reviews when product is deleted
    reviews = relationship(
        "Review",
        back_populates="product",
        cascade="all, delete-orphan",
    )


# ── 3. customers ───────────────────────────────────────────────────────────────
#   Central entity. Owns orders and reviews.
#   Soft-delete (is_active) — we never hard-delete customers because their
#   order history must remain intact for reporting.
# ───────────────────────────────────────────────────────────────────────────────
class Customer(Base):
    __tablename__ = "customers"

    id         = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name  = Column(String(100), nullable=False)
    email      = Column(String(200), unique=True, nullable=False, index=True)
    phone      = Column(String(20))
    address    = Column(Text)
    city       = Column(String(100))
    state      = Column(String(100))
    country    = Column(String(100), default="Nigeria", nullable=False)
    postal_code= Column(String(20))
    password   = Column(String(255), nullable=False)
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    # One-to-many: one customer → many orders
    orders  = relationship(
        "Order",
        back_populates="customer",
        passive_deletes=True,   # RESTRICT at DB level — can't delete customer with orders
    )

    # One-to-many: cascade delete reviews when customer is deleted
    reviews = relationship(
        "Review",
        back_populates="customer",
        cascade="all, delete-orphan",
    )


# ── 4. coupons ─────────────────────────────────────────────────────────────────
#   Optional relationship to orders (nullable FK on orders.coupon_id).
#   Business rule: used_count must not exceed max_uses — enforced in app layer.
# ───────────────────────────────────────────────────────────────────────────────
class Coupon(Base):
    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint("discount_pct > 0 AND discount_pct <= 100", name="ck_coupons_discount_range"),
        CheckConstraint("used_count >= 0",                          name="ck_coupons_used_count_non_negative"),
        CheckConstraint("max_uses > 0",                             name="ck_coupons_max_uses_positive"),
    )

    id           = Column(Integer, primary_key=True, index=True)
    code         = Column(String(50), unique=True, nullable=False, index=True)
    discount_pct = Column(Numeric(5, 2), nullable=False)   # e.g. 10.00 = 10%
    max_uses     = Column(Integer, default=100, nullable=False)
    used_count   = Column(Integer, default=0,   nullable=False)
    is_active    = Column(Boolean, default=True, nullable=False)
    expires_at   = Column(DateTime(timezone=True))
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # One-to-many: a coupon can be used by many orders
    # SET NULL on delete: deleting a coupon doesn't break order history
    orders = relationship("Order", back_populates="coupon")


# ── 5. orders ──────────────────────────────────────────────────────────────────
#   Core transaction record.
#   FK to customers (RESTRICT — can't delete customer with orders).
#   FK to coupons (SET NULL — coupon may be deleted without losing order data).
#   Parent of order_items, payment (1:1), shipping (1:1).
# ───────────────────────────────────────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("subtotal >= 0",        name="ck_orders_subtotal_non_negative"),
        CheckConstraint("discount_amount >= 0", name="ck_orders_discount_non_negative"),
        CheckConstraint("total >= 0",           name="ck_orders_total_non_negative"),
        Index("ix_orders_customer_created", "customer_id", "created_at"),   # speeds up "orders by customer sorted by date"
    )

    id              = Column(Integer, primary_key=True, index=True)
    customer_id     = Column(
        Integer,
        ForeignKey("customers.id", ondelete="RESTRICT"),  # preserve order history
        nullable=False,
        index=True,
    )
    coupon_id       = Column(
        Integer,
        ForeignKey("coupons.id", ondelete="SET NULL"),    # coupon deleted → order still intact
        nullable=True,
        index=True,
    )
    status          = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    subtotal        = Column(Numeric(10, 2), nullable=False)
    discount_amount = Column(Numeric(10, 2), default=0, nullable=False)
    total           = Column(Numeric(10, 2), nullable=False)
    notes           = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────────
    customer = relationship("Customer", back_populates="orders")
    coupon   = relationship("Coupon",   back_populates="orders")

    # Cascade: deleting an order removes its line items, payment, and shipping
    items    = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment  = relationship("Payment",   back_populates="order", uselist=False, cascade="all, delete-orphan")
    shipping = relationship("Shipping",  back_populates="order", uselist=False, cascade="all, delete-orphan")


# ── 6. order_items ─────────────────────────────────────────────────────────────
#   Junction between orders and products with extra data (price snapshot).
#   unit_price is a SNAPSHOT of the product price at time of purchase —
#   critical so historical orders aren't affected by future price changes.
#   UniqueConstraint prevents duplicate product rows within the same order.
# ───────────────────────────────────────────────────────────────────────────────
class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),  # one row per product per order
        CheckConstraint("quantity > 0",       name="ck_order_items_quantity_positive"),
        CheckConstraint("unit_price > 0",     name="ck_order_items_unit_price_positive"),
        CheckConstraint("total_price > 0",    name="ck_order_items_total_price_positive"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    order_id    = Column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),   # line items die with the order
        nullable=False,
        index=True,
    )
    product_id  = Column(
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),  # can't delete a product that's been ordered
        nullable=False,
        index=True,
    )
    quantity    = Column(Integer, nullable=False)
    unit_price  = Column(Numeric(10, 2), nullable=False)   # price snapshot at time of order
    total_price = Column(Numeric(10, 2), nullable=False)   # quantity × unit_price
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    order   = relationship("Order",   back_populates="items")
    product = relationship("Product", back_populates="order_items")


# ── 7. payments ────────────────────────────────────────────────────────────────
#   Strict one-to-one with orders (unique FK).
#   Cascades from order: deleting an order deletes its payment record.
# ───────────────────────────────────────────────────────────────────────────────
class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
    )

    id        = Column(Integer, primary_key=True, index=True)
    order_id  = Column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),  # payment deleted with order
        unique=True,    # enforces strict one-to-one at DB level
        nullable=False,
    )
    method    = Column(Enum(PaymentMethod), nullable=False)
    status    = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    amount    = Column(Numeric(10, 2), nullable=False)
    reference = Column(String(100), unique=True)   # external payment gateway reference
    created_at= Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at= Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    order = relationship("Order", back_populates="payment")


# ── 8. shipping ────────────────────────────────────────────────────────────────
#   Strict one-to-one with orders (unique FK).
#   Stores destination address as a SNAPSHOT (customer may change address later).
#   Cascades from order.
# ───────────────────────────────────────────────────────────────────────────────
class Shipping(Base):
    __tablename__ = "shipping"

    id              = Column(Integer, primary_key=True, index=True)
    order_id        = Column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),  # shipping record deleted with order
        unique=True,   # one shipping record per order
        nullable=False,
    )
    status          = Column(Enum(ShippingStatus), default=ShippingStatus.not_shipped, nullable=False)
    carrier         = Column(String(100))
    tracking_number = Column(String(100))
    # Address snapshot — independent of customer.address so history is preserved
    address         = Column(Text, nullable=False)
    city            = Column(String(100))
    state           = Column(String(100))
    country         = Column(String(100), nullable=False)
    postal_code     = Column(String(20))
    shipped_at      = Column(DateTime(timezone=True))
    delivered_at    = Column(DateTime(timezone=True))
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at      = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    order = relationship("Order", back_populates="shipping")


# ── 9. inventory ───────────────────────────────────────────────────────────────
#   Strict one-to-one with products (unique FK).
#   Cascade: inventory row is deleted when its product is deleted.
# ───────────────────────────────────────────────────────────────────────────────
class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity >= 0",    name="ck_inventory_quantity_non_negative"),
        CheckConstraint("reorder_lvl >= 0", name="ck_inventory_reorder_non_negative"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    product_id  = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),  # inventory dies with product
        unique=True,   # enforces one-to-one at DB level
        nullable=False,
    )
    quantity    = Column(Integer, default=0,  nullable=False)
    reorder_lvl = Column(Integer, default=10, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    product = relationship("Product", back_populates="inventory")


# ── 10. reviews ────────────────────────────────────────────────────────────────
#   One customer can review one product only once (UniqueConstraint).
#   Cascades from both product and customer.
# ───────────────────────────────────────────────────────────────────────────────
class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("product_id", "customer_id", name="uq_reviews_product_customer"),  # one review per customer per product
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    product_id  = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),   # review deleted with product
        nullable=False,
        index=True,
    )
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),  # review deleted with customer
        nullable=False,
        index=True,
    )
    rating    = Column(Integer, nullable=False)   # 1–5, enforced by CheckConstraint
    comment   = Column(Text)
    created_at= Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at= Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    product  = relationship("Product",  back_populates="reviews")
    customer = relationship("Customer", back_populates="reviews")
