from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, DECIMAL
from .session import Base
from datetime import datetime

class HotspotUser(Base):
    __tablename__ = "hotspot_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(20), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    otp = Column(String(50), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice = Column(String(125), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    user_type = Column(String(50), nullable=False)
    user_id = Column(Integer, nullable=False)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=False)
    phone_number = Column(String(20), nullable=True)
    #router_id = Column(Integer, ForeignKey("routers.id"), nullable=True)

class Router(Base):
    __tablename__ = "routers"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(125), nullable=False)
    ip_address = Column(String(125), nullable=False)
    username = Column(String(125), nullable=False)
    password = Column(String(125), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Package(Base):
    __tablename__ = "packages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(125), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    service_type = Column(String(50), nullable=False)
    validity_days = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PPPUser(Base):
    __tablename__ = "ppp_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(125), nullable=False)
    email = Column(String(125), unique=True, nullable=False)
    pppoe_username = Column(String(125), unique=True, nullable=False)
    pppoe_password = Column(String(125), nullable=False)
    mobile_number = Column(String(20), nullable=False)
    profile = Column(Text, nullable=True)
    expires_on = Column(DateTime, nullable=True)
    location = Column(String(125), nullable=True)
    apartment = Column(String(125), nullable=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    role = Column(String(125), nullable=False, default="ppp_user")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
