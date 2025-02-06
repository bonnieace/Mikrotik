from sqlalchemy.orm import Session
from .models import HotspotUser, Payment, Log

# Hotspot User CRUD
def create_hotspot_user(db: Session, phone_number: str, amount: float, otp: str):
    """
    Create a new hotspot user.
    Save the provided OTP (which will be the username) into the `otp` field.
    """
    db_user = HotspotUser(
        phone_number=phone_number,
        amount=amount,
        otp=otp  # Save the username as OTP
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