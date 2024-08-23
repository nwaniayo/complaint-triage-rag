
from database import init_db, SessionLocal
from models import Product, SubProduct, Complaint
from complaint_storage import store_complaint

# Initialize the database (ensure the tables are created)
init_db()

# Test data
dummy_product_name = "Test Product"
dummy_sub_product_name = "Test Sub-product"
dummy_complaint_text = "This is a test complaint for the sub-product."

# Call the store_complaint function with the dummy data
store_complaint(dummy_product_name, dummy_sub_product_name, dummy_complaint_text)

# Verify the data was stored correctly
session = SessionLocal()

# Query the product
stored_product = session.query(Product).filter_by(name=dummy_product_name).first()
print(f"Stored Product: {stored_product.name}")

# Query the sub-product
stored_sub_product = session.query(SubProduct).filter_by(name=dummy_sub_product_name).first()
print(f"Stored Sub-product: {stored_sub_product.name}")

# Query the complaint
stored_complaint = session.query(Complaint).filter_by(sub_product_id=stored_sub_product.id).first()
print(f"Stored Complaint: {stored_complaint.complaint}")

# Close the session
session.close()
