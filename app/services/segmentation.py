from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
from app.models.models import Customer, Order, Segment
import uuid

# --- The core engine ---

async def get_segment_customers(filters: dict, db: AsyncSession) -> list[Customer]:
    """
    Takes a filter dict and returns matching customers.
    
    Supported filters:
      inactive_days     — last order was N+ days ago
      active_days       — last order was within N days
      min_spend         — total_spend >= value
      max_spend         — total_spend <= value
      min_orders        — order_count >= value
      city              — exact city match
      preferred_channel — whatsapp / sms / email / rcs
    """
    conditions = []

    if "inactive_days" in filters:
        cutoff = datetime.utcnow() - timedelta(days=filters["inactive_days"])
        conditions.append(Customer.last_order_date <= cutoff)

    if "active_days" in filters:
        cutoff = datetime.utcnow() - timedelta(days=filters["active_days"])
        conditions.append(Customer.last_order_date >= cutoff)

    if "min_spend" in filters:
        conditions.append(Customer.total_spend >= filters["min_spend"])

    if "max_spend" in filters:
        conditions.append(Customer.total_spend <= filters["max_spend"])

    if "min_orders" in filters:
        conditions.append(Customer.order_count >= filters["min_orders"])

    if "city" in filters:
        conditions.append(Customer.city == filters["city"])

    if "preferred_channel" in filters:
        conditions.append(Customer.preferred_channel == filters["preferred_channel"])

    query = select(Customer)
    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    return result.scalars().all()


async def create_segment(
    name: str,
    description: str,
    filters: dict,
    db: AsyncSession
) -> Segment:
    """Creates and saves a segment, computing customer count immediately."""
    
    customers = await get_segment_customers(filters, db)
    
    segment = Segment(
        id=uuid.uuid4(),
        name=name,
        description=description,
        filters=filters,
        customer_count=len(customers)
    )
    db.add(segment)
    await db.commit()
    await db.refresh(segment)
    return segment


async def refresh_segment_count(segment: Segment, db: AsyncSession) -> int:
    """Recalculates and updates customer count for a segment."""
    customers = await get_segment_customers(segment.filters, db)
    segment.customer_count = len(customers)
    await db.commit()
    return segment.customer_count