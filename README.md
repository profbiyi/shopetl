# ShopETL — Teaching E-commerce API

A lightweight e-commerce backend for teaching ETL with pandas.
Built with FastAPI + PostgreSQL.

---

## Project Structure

```
ecommerce/
├── main.py                         # FastAPI app entry point
├── requirements.txt
├── Procfile                        # Railway deployment
├── .env.example                    # Copy to .env and fill in
├── app/
│   ├── database.py                 # SQLAlchemy engine + session
│   ├── auth.py                     # JWT + password hashing
│   ├── models/
│   │   └── models.py               # All 10 SQLAlchemy models
│   └── routers/
│       ├── customers.py            # Register, login, /me
│       ├── products.py             # List products & categories
│       ├── orders.py               # Place & view orders
│       └── reviews.py              # Product reviews
├── frontend/
│   └── index.html                  # Simple storefront UI
└── seed/
    ├── seed_base.py                # Load categories, products, coupons
    └── simulate_transactions.py   # Bulk fake transaction generator
```

---

## Tables

| Table         | Description                              |
|---------------|------------------------------------------|
| customers     | Registered users                         |
| categories    | Product categories                       |
| products      | Items for sale                           |
| inventory     | Stock levels per product                 |
| orders        | Customer orders                          |
| order_items   | Line items per order                     |
| payments      | Payment per order                        |
| shipping      | Shipping record per order                |
| reviews       | Customer product reviews                 |
| coupons       | Discount codes                           |

---

## Deploy to Railway

### 1. Push code to GitHub
Create a new GitHub repo and push the `ecommerce/` folder to it.

### 2. Create a Railway project
- Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
- Select your repository

### 3. Add a PostgreSQL database
In your Railway project → **New Service → Database → PostgreSQL**

### 4. Set Environment Variables
In Railway → your FastAPI service → **Variables** tab:
```
DATABASE_URL=${{Postgres.DATABASE_URL}}   ← Railway auto-fills this if you use the reference
SECRET_KEY=<generate one below>
```

Generate a secret key locally:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 5. The app auto-creates all tables on startup
No migrations needed. Tables are created automatically when the service starts.

### 6. Seed the Database
Copy the **public** `DATABASE_URL` from Railway → PostgreSQL service → **Variables** tab
(use the one labeled `DATABASE_PUBLIC_URL` — this works from outside Railway's network).

Then run locally:
```bash
pip install -r requirements.txt

# Copy .env.example to .env and paste in the DATABASE_PUBLIC_URL
cp .env.example .env

# Step 1 — Load base data (products, categories, coupons)
python seed/seed_base.py

# Step 2 — Simulate bulk transactions
python seed/simulate_transactions.py --customers 50 --orders 200
```

### 7. Enable public database access for students
By default Railway's PostgreSQL is private. To let students connect directly:

1. Railway → your **PostgreSQL service** → **Settings** tab
2. Under **Networking** → click **Add Public Networking**
3. Copy the `DATABASE_PUBLIC_URL` — this is what students use

> **Note:** The public URL uses a different port (not 5432). Railway assigns a random port.
> The full URL looks like: `postgresql://postgres:PASSWORD@HOST.railway.app:PORT/railway`

### Share with students
Give students the `DATABASE_PUBLIC_URL` from Railway's PostgreSQL Variables tab:
```python
from sqlalchemy import create_engine

# Paste the DATABASE_PUBLIC_URL from Railway here
engine = create_engine("postgresql://postgres:PASSWORD@HOST.railway.app:PORT/railway")
```

---

## API Endpoints

| Method | Endpoint                  | Auth | Description              |
|--------|---------------------------|------|--------------------------|
| POST   | /customers/register       | No   | Register new customer    |
| POST   | /customers/login          | No   | Login → get JWT token    |
| GET    | /customers/me             | Yes  | Current user info        |
| GET    | /products/                | No   | List all products        |
| GET    | /products/categories/all  | No   | List categories          |
| POST   | /orders/                  | Yes  | Place an order           |
| GET    | /orders/my-orders         | Yes  | Customer's orders        |
| POST   | /reviews/                 | Yes  | Leave a product review   |
| GET    | /health                   | No   | Health check             |

Interactive docs: `https://your-app.railway.app/docs`

---

## ETL Exercise — pandas Full Load

```python
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("YOUR_DATABASE_URL")

# Full load — all orders
orders_df    = pd.read_sql("SELECT * FROM orders", engine)
customers_df = pd.read_sql("SELECT * FROM customers", engine)
products_df  = pd.read_sql("SELECT * FROM products", engine)
items_df     = pd.read_sql("SELECT * FROM order_items", engine)

print(orders_df.shape)
```

---

## ETL Exercise — pandas Incremental Load

```python
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

engine = create_engine("YOUR_DATABASE_URL")

# Save this after each run
last_watermark = "2024-01-01 00:00:00"

new_orders = pd.read_sql(f"""
    SELECT * FROM orders
    WHERE updated_at > '{last_watermark}'
    ORDER BY updated_at
""", engine)

print(f"New orders since last run: {len(new_orders)}")

# Update watermark
if len(new_orders):
    last_watermark = str(new_orders['updated_at'].max())
```

---

## Coupons for Manual Testing

| Code       | Discount |
|------------|----------|
| WELCOME10  | 10% off  |
| SAVE20     | 20% off  |
| FLASH50    | 50% off  |
