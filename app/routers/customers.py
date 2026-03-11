from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_db
from app.models.models import Customer
from app.auth import hash_password, verify_password, create_access_token, decode_token

router = APIRouter(prefix="/customers", tags=["Customers"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/customers/login")


# ── Schemas ───────────────────────────────────────────────────────────────────
class CustomerRegister(BaseModel):
    first_name:  str
    last_name:   str
    email:       EmailStr
    phone:       Optional[str] = None
    address:     Optional[str] = None
    city:        Optional[str] = None
    state:       Optional[str] = None
    country:     str = "Nigeria"
    postal_code: Optional[str] = None
    password:    str


class CustomerUpdate(BaseModel):
    first_name:  Optional[str] = None
    last_name:   Optional[str] = None
    phone:       Optional[str] = None
    address:     Optional[str] = None
    city:        Optional[str] = None
    state:       Optional[str] = None
    country:     Optional[str] = None
    postal_code: Optional[str] = None


class CustomerOut(BaseModel):
    id:          int
    first_name:  str
    last_name:   str
    email:       str
    phone:       Optional[str]
    address:     Optional[str]
    city:        Optional[str]
    state:       Optional[str]
    country:     str
    postal_code: Optional[str]
    is_active:   bool

    class Config:
        from_attributes = True


# ── Dependency: current customer from JWT ─────────────────────────────────────
def get_current_customer(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    customer = db.query(Customer).filter(Customer.id == int(payload.get("sub"))).first()
    if not customer or not customer.is_active:
        raise HTTPException(status_code=401, detail="Customer not found or inactive")
    return customer


# ── Routes ────────────────────────────────────────────────────────────────────
@router.post("/register", response_model=CustomerOut, status_code=201)
def register(data: CustomerRegister, db: Session = Depends(get_db)):
    if db.query(Customer).filter(Customer.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    customer = Customer(
        **data.model_dump(exclude={"password"}),
        password=hash_password(data.password),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.email == form.username).first()
    if not customer or not verify_password(form.password, customer.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(customer.id), "email": customer.email})
    return {"access_token": token, "token_type": "bearer", "customer": CustomerOut.model_validate(customer)}


@router.get("/me", response_model=CustomerOut)
def me(current: Customer = Depends(get_current_customer)):
    return current


@router.patch("/me", response_model=CustomerOut)
def update_me(data: CustomerUpdate, db: Session = Depends(get_db), current: Customer = Depends(get_current_customer)):
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(current, field, value)
    db.commit()
    db.refresh(current)
    return current
