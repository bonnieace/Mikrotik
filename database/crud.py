from sqlalchemy.orm import Session
from .models import HotspotUser, PPPUser, Payment, Log , Package

# Hotspot User CRUD
def create_hotspot_user(db: Session, phone_number: str, amount: float, otp: str):
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
        created_at=created_at
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Payment CRUD
def create_payment(db: Session, invoice: str, amount: float, user_type: str, user_id: int):
    db_payment = Payment(invoice=invoice, amount=amount, user_type=user_type, user_id=user_id)
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment

# Log CRUD
def create_log(db: Session, description: str, phone_number: str = None):
    db_log = Log(description=description, phone_number=phone_number)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


#create package
def create_package(db: Session, name: str, description: str, price: float, service_type: str, validity_days: int):
    db_package = Package(name=name, description=description, price=price, service_type=service_type, validity_days=validity_days)
    db.add(db_package)
    db.commit()
    db.refresh(db_package)
    return db_package

#read all payments
def get_payments(db: Session):
    return db.query(Payment).all()

#read payments by user type
def get_payments_by_user_type(db: Session, user_type: str):
    return db.query(Payment).filter(Payment.user_type == user_type).all()


#read all logs
def get_logs(db: Session):
    return db.query(Log).all()

#read all packages
def get_packages(db: Session):
    return db.query(Package).all()

#read all hotspot users
def get_hotspot_users(db: Session):
    return db.query(HotspotUser).all()

#create ppp user
def create_ppp_user(db: Session, name: str):
    db_ppp_user = PPPUser(name=name)
    db.add(db_ppp_user)
    db.commit()
    db.refresh(db_ppp_user)
    return db_ppp_user

#get ppp users
def get_ppp_users(db: Session):
    return db.query(PPPUser).all()

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