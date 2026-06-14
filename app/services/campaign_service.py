import uuid
import httpx
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import (
    Campaign, Message, CampaignEvent,
    CampaignStatus, MessageStatus, Segment, Customer
)
from app.services.segmentation import get_segment_customers

CHANNEL_SERVICE_URL = "http://localhost:8001/send"


def personalise_message(template: str, customer: Customer) -> str:
    """
    Simple personalisation — replaces placeholders with customer data.
    e.g. "Hi {{name}}, ..." becomes "Hi Priya, ..."
    """
    return (
        template
        .replace("{{name}}", customer.name.split()[0])
        .replace("{{city}}", customer.city or "")
        .replace("{{total_spend}}", f"₹{int(customer.total_spend):,}")
    )


async def launch_campaign(campaign_id: str, db: AsyncSession):
    """
    Core campaign launch logic:
    1. Load campaign + segment customers
    2. Create a Message row for each customer
    3. Fire off send requests to channel service
    4. Update campaign status
    """

    # Load campaign
    result = await db.execute(
        select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    # Load segment
    seg_result = await db.execute(
        select(Segment).where(Segment.id == campaign.segment_id)
    )
    segment = seg_result.scalar_one_or_none()
    if not segment:
        raise ValueError(f"Segment not found")

    # Get customers in this segment
    customers = await get_segment_customers(segment.filters, db)
    if not customers:
        raise ValueError("No customers in segment")

    # Update campaign status to running
    campaign.status = CampaignStatus.running
    campaign.sent_at = datetime.utcnow()
    campaign.total_sent = len(customers)
    await db.commit()

    # Create message rows + fire sends
    async with httpx.AsyncClient(timeout=10) as client:
        for customer in customers:
            msg_id = uuid.uuid4()
            content = personalise_message(campaign.message_template, customer)

            # Create message row
            message = Message(
                id=msg_id,
                campaign_id=campaign.id,
                customer_id=customer.id,
                channel=campaign.channel,
                content=content,
                status=MessageStatus.queued,
            )
            db.add(message)
            await db.flush()   # write to db but don't commit yet

            # Fire and forget to channel service
            try:
                await client.post(CHANNEL_SERVICE_URL, json={
                    "message_id": str(msg_id),
                    "recipient_phone": customer.phone,
                    "recipient_email": customer.email,
                    "channel": campaign.channel.value,
                    "content": content,
                })
            except Exception as e:
                # If channel service is down, mark as failed
                message.status = MessageStatus.failed
                campaign.total_failed = (campaign.total_failed or 0) + 1

    campaign.status = CampaignStatus.completed
    await db.commit()