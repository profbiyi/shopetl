from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.database import engine
from app.models.models import Base
from app.routers import customers, products, orders, reviews

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="🛒 ETL Teaching E-commerce API",
    description="A simple e-commerce backend for learning ETL with pandas",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(customers.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(reviews.router)

# Serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "message": "E-commerce API is running!"}
