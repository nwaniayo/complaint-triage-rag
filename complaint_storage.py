from sqlalchemy.orm import Session
from database import SessionLocal
from models import Product, SubProduct, Complaint

def store_complaint(product_name: str, sub_product_name: str, complaint_text: str):
    try:
        # Create a new session
        session = SessionLocal()
        
        # Check if the product already exists
        product = session.query(Product).filter_by(name=product_name).first()
        if not product:
            # Create and add the product if it doesn't exist
            product = Product(name=product_name)
            session.add(product)
            session.commit()
            print(f"Added new product: {product_name}")
        
        # Check if the sub-product already exists
        sub_product = session.query(SubProduct).filter_by(name=sub_product_name).first()
        if not sub_product:
            # Create and add the sub-product if it doesn't exist
            sub_product = SubProduct(name=sub_product_name, product_id=product.id)
            session.add(sub_product)
            session.commit()
            print(f"Added new sub-product: {sub_product_name}")
        
        # Create and add the complaint
        complaint = Complaint(complaint=complaint_text, sub_product_id=sub_product.id)
        session.add(complaint)
        session.commit()
        print(f"Complaint stored successfully: Product={product_name}, Sub-product={sub_product_name}")
        
    except Exception as e:
        # Log any errors that occur
        print(f"Error storing complaint: {e}")
        raise e
    finally:
        # Ensure the session is closed
        session.close()
