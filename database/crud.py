from sqlalchemy.orm import Session
from .models import HotspotUser, PPPUser, Payment, Log, Package, Router, AdminUser
from typing import Optional

# Hotspot User CRUD
def create_hotspot_user(db: Session, phone_number: str, amount: float, otp: str, router_id: int = None):
    """
    Create a new hotspot user.
    Save the provided OTP (which will be the username) into the `otp` field.
    """
    created_at = datetime.now()
    expires_at=calculate_expires_at(created_at, amount)
    db_user = HotspotUser(
        phone_number=phone_number,
        amount=amount,
        otp=otp , # Save the username as OTP
        expires_at=expires_at,
        created_at=created_at,
        router_id=router_id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Payment CRUD
def create_payment(db: Session, invoice: str, amount: float, user_type: str, user_id: int, router_id: int = None):
    db_payment = Payment(invoice=invoice, amount=amount, user_type=user_type, user_id=user_id, router_id=router_id)
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

# Log CRUD
def create_log(db: Session, description: str, phone_number: str = None, router_id: int = None):
    db_log = Log(description=description, phone_number=phone_number, router_id=router_id)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


#create package
def create_package(db: Session, name: str, description: str, price: float, service_type: str, validity_days: int, router_id: int = None):
    db_package = Package(name=name, description=description, price=price, service_type=service_type, validity_days=validity_days, router_id=router_id)
    db.add(db_package)
    db.commit()
    db.refresh(db_package)
    return db_package

#read all payments
def get_payments(db: Session, router_id: Optional[int] = None):
    query = db.query(Payment)
    if router_id is not None:
        query = query.filter(Payment.router_id == router_id)
    return query.all()

#read payments by user type
def get_payments_by_user_type(db: Session, user_type: str, router_id: Optional[int] = None):
    query = db.query(Payment).filter(Payment.user_type == user_type)
    if router_id is not None:
        query = query.filter(Payment.router_id == router_id)
    return query.all()

#read payment totals for the current day by user type
def get_payment_totals_for_today_by_user_type(db: Session, user_type: str, router_id: Optional[int] = None):
    today = datetime.now().date()
    query = db.query(Payment).filter(
        Payment.user_type == user_type,
        Payment.created_at >= today
    )
    if router_id is not None:
        query = query.filter(Payment.router_id == router_id)
    payments = query.all()
    total_amount = sum(payment.amount for payment in payments)
    return total_amount

#read all logs
def get_logs(db: Session, router_id: Optional[int] = None):
    query = db.query(Log)
    if router_id is not None:
        query = query.filter(Log.router_id == router_id)
    return query.all()

#read all packages
def get_packages(db: Session, router_id: Optional[int] = None):
    query = db.query(Package)
    if router_id is not None:
        query = query.filter(Package.router_id == router_id)
    return query.all()

#read all hotspot users
def get_hotspot_users(db: Session, router_id: Optional[int] = None):
    query = db.query(HotspotUser)
    if router_id is not None:
        query = query.filter(HotspotUser.router_id == router_id)
    return query.all()

#create ppp user
def create_ppp_user(db: Session, name,email,pppoe_username,pppoe_password,mobile_number,location,apartment,profile: str, router_id: int = None):
    db_ppp_user = PPPUser(name=name,email=email,pppoe_password=pppoe_password,mobile_number=mobile_number,location=location,apartment=apartment,profile=profile,pppoe_username=pppoe_username,router_id=router_id)
    db.add(db_ppp_user)
    db.commit()
    db.refresh(db_ppp_user)
    return db_ppp_user

#get ppp users
def get_ppp_users(db: Session, router_id: Optional[int] = None):
    query = db.query(PPPUser)
    if router_id is not None:
        query = query.filter(PPPUser.router_id == router_id)
    return query.all()

# Router CRUD
def create_router(db: Session, name: str, ip_address: str, port: int, username: str, password: str, owner_id: int = None):
    db_router = Router(
        name=name,
        ip_address=ip_address,
        port=port,
        username=username,
        password=password,
        owner_id=owner_id,
    )
    db.add(db_router)
    db.commit()
    db.refresh(db_router)
    return db_router

def get_routers(db: Session, owner_id: Optional[int] = None):
    query = db.query(Router)
    if owner_id is not None:
        query = query.filter(Router.owner_id == owner_id)
    return query.all()

def get_router_by_id(db: Session, router_id: int):
    return db.query(Router).filter(Router.id == router_id).first()

def update_router(db: Session, router_id: int, **kwargs):
    router = db.query(Router).filter(Router.id == router_id).first()
    if router is None:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(router, key, value)
    db.commit()
    db.refresh(router)
    return router

def delete_router(db: Session, router_id: int):
    router = db.query(Router).filter(Router.id == router_id).first()
    if router is None:
        return False
    db.delete(router)
    db.commit()
    return True

# AdminUser CRUD
def create_admin_user(db: Session, username: str, hashed_password: str, role: str = "isp", email: str = None):
    db_user = AdminUser(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_admin_user_by_username(db: Session, username: str):
    return db.query(AdminUser).filter(AdminUser.username == username).first()

def get_admin_user_by_id(db: Session, user_id: int):
    return db.query(AdminUser).filter(AdminUser.id == user_id).first()

def list_admin_users(db: Session):
    return db.query(AdminUser).all()

from datetime import datetime, timedelta
# Mapping of amount to duration
UPTIME_MAPPING = {
    1: "1h",    # 1 hour
    50: "1d",   # 1 day
    150: "3d",  # 3 days
    300: "1w",  # 1 week
    1000: "4w", # 4 weeks
}
def calculate_expires_at(created_at: datetime, amount: int) -> datetime:
    """
    Calculate the expiration time based on the amount paid.
    """
    duration = UPTIME_MAPPING.get(amount)
    if not duration:
        return None  # No expiration if amount is not in the mapping

    # Parse the duration string (e.g., "1h", "3d", "1w")
    if duration.endswith("h"):
        hours = int(duration[:-1])
        return created_at + timedelta(hours=hours)
    elif duration.endswith("d"):
        days = int(duration[:-1])
        return created_at + timedelta(days=days)
    elif duration.endswith("w"):
        weeks = int(duration[:-1])
        return created_at + timedelta(weeks=weeks)
    else:
        return None