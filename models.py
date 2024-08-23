# models.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    sub_products = relationship("SubProduct", back_populates="product")

class SubProduct(Base):
    __tablename__ = 'subproducts'

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete="CASCADE"), nullable=False)
    name = Column(String, unique=True, nullable=False)
    product = relationship("Product", back_populates="sub_products")
    complaints = relationship("Complaint", back_populates="sub_product")

class Complaint(Base):
    __tablename__ = 'complaints'

    id = Column(Integer, primary_key=True, index=True)
    sub_product_id = Column(Integer, ForeignKey('subproducts.id', ondelete="CASCADE"), nullable=False)
    complaint = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    sub_product = relationship("SubProduct", back_populates="complaints")
