import asyncio
import random
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import uuid
import sys

load_dotenv()

from app.models.models import (
    Base, Customer, Order, ChannelType
)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# --- Realistic data pools ---

FIRST_NAMES = [
    "Priya", "Ananya", "Riya", "Sneha", "Kavya",
    "Arjun", "Rohit", "Vikram", "Aditya", "Karan",
    "Meera", "Divya", "Pooja", "Nisha", "Sunita",
    "Rahul", "Amit", "Suresh", "Deepak", "Nikhil",
    "Lakshmi", "Geeta", "Anjali", "Swati", "Pallavi"
]

LAST_NAMES = [
    "Sharma", "Patel", "Iyer", "Reddy", "Nair",
    "Singh", "Gupta", "Mehta", "Joshi", "Kumar",
    "Pillai", "Menon", "Rao", "Shah", "Verma"
]

CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune", "Kolkata", "Jaipur"]

CHANNELS = [ChannelType.whatsapp, ChannelType.sms, ChannelType.email, ChannelType.rcs]
CHANNEL_WEIGHTS = [0.5, 0.2, 0.2, 0.1]   # WhatsApp is most popular

PRODUCTS = [
    {"name": "Floral Kurta", "price": 1299},
    {"name": "Silk Saree", "price": 4999},
    {"name": "Denim Jacket", "price": 2499},
    {"name": "Linen Trousers", "price": 1799},
    {"name": "Embroidered Dupatta", "price": 899},
    {"name": "Cotton Anarkali", "price": 2199},
    {"name": "Printed Maxi Dress", "price": 1599},
    {"name": "Wool Shawl", "price": 1199},
    {"name": "Block Print Suit", "price": 3299},
    {"name": "Chiffon Blouse", "price": 799},
]

def random_date(days_ago_min, days_ago_max):
    days_ago = random.randint(days_ago_min, days_ago_max)
    return datetime.utcnow() - timedelta(days=days_ago)

def make_customer(i):
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    email = f"{first.lower()}.{last.lower()}{i}@gmail.com"
    phone = f"+91{random.randint(7000000000, 9999999999)}"
    city = random.choice(CITIES)
    channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]
    return Customer(
        id=uuid.uuid4(),
        name=name,
        email=email,
        phone=phone,
        city=city,
        preferred_channel=channel,
        total_spend=0.0,
        order_count=0,
        last_order_date=None,
    )

def make_orders_for_customer(customer, customer_type):
    """
    customer_type controls behaviour:
      'vip'      — high spend, recent orders
      'regular'  — moderate spend, some recent
      'lapsed'   — used to buy, gone quiet (60-120 days ago)
      'new'      — only 1-2 orders, very recent
      'dormant'  — 1 old order, never came back
    """
    orders = []

    if customer_type == "vip":
        num_orders = random.randint(8, 15)
        recency_range = (2, 30)
    elif customer_type == "regular":
        num_orders = random.randint(3, 7)
        recency_range = (10, 60)
    elif customer_type == "lapsed":
        num_orders = random.randint(3, 6)
        recency_range = (60, 120)
    elif customer_type == "new":
        num_orders = random.randint(1, 2)
        recency_range = (1, 14)
    else:  # dormant
        num_orders = 1
        recency_range = (120, 365)

    total_spend = 0.0
    latest_date = None

    for _ in range(num_orders):
        product = random.choice(PRODUCTS)
        qty = random.randint(1, 3)
        amount = product["price"] * qty
        ordered_at = random_date(*recency_range)

        orders.append(Order(
            id=uuid.uuid4(),
            customer_id=customer.id,
            amount=amount,
            items=[{"name": product["name"], "qty": qty, "price": product["price"]}],
            ordered_at=ordered_at,
        ))

        total_spend += amount
        if latest_date is None or ordered_at > latest_date:
            latest_date = ordered_at

    # update denormalised fields on customer
    customer.total_spend = round(total_spend, 2)
    customer.order_count = num_orders
    customer.last_order_date = latest_date

    return orders


async def seed():
    async with engine.begin() as conn:
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created.")

    # customer type distribution across 50 customers
    customer_types = (
        ["vip"] * 8 +
        ["regular"] * 15 +
        ["lapsed"] * 12 +
        ["new"] * 10 +
        ["dormant"] * 5
    )
    random.shuffle(customer_types)

    async with AsyncSessionLocal() as session:
        print("Seeding customers and orders...")
        for i, ctype in enumerate(customer_types):
            customer = make_customer(i)
            orders = make_orders_for_customer(customer, ctype)
            session.add(customer)
            for order in orders:
                session.add(order)

        await session.commit()
        print(f"Done! Seeded {len(customer_types)} customers.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())