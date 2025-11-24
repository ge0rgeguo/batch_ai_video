import sys
import os

# Add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server.db import engine, Base
from server.models import RechargeOrder

def migrate():
    print("Creating recharge_orders table...")
    # Use SQLAlchemy to create the table if it doesn't exist
    RechargeOrder.__table__.create(bind=engine, checkfirst=True)
    print("Done.")

if __name__ == "__main__":
    migrate()

