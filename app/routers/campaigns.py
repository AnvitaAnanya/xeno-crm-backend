from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models.models import (
    Campaign, Message, CampaignEvent,
    CampaignStatus, MessageStatus, Segment
)
from app.services.campaign_service import launch_campaign
import uuid

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# --- Schemas ---

class CampaignCreate(BaseModel):
    name: str
    segment_id: str
    channel: str
    message_template: str


class CampaignResponse(BaseModel):
    id: str
    name: str
    segment_id: str
    channel: str
    message_template: str
    status: str
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_failed: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReceiptPayload(BaseModel):
    message_id: str
    event: str
    occurred_at: str


# --- Endpoints ---

@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db)
):
    campaign = Campaign(
        id=uuid.uuid4(),
        name=payload.name,
        segment_id=uuid.UUID(payload.segment_id),
        channel=payload.channel,
        message_template=payload.message_template,
        status=CampaignStatus.draft,
        total_sent=0,
        total_delivered=0,
        total_opened=0,
        total_clicked=0,
        total_failed=0,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return _campaign_to_response(campaign)


@router.post("/{campaign_id}/launch")
async def launch(
    campaign_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Launches campaign in background so API returns immediately."""
    background_tasks.add_task(launch_campaign, campaign_id, db)
    return {"status": "launching", "campaign_id": campaign_id}


@router.get("/", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Campaign).order_by(Campaign.created_at.desc())
    )
    campaigns = result.scalars().all()
    return [_campaign_to_response(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Campaign).where(Campaign.id == uuid.UUID(campaign_id))
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _campaign_to_response(campaign)


@router.post("/receipt")
async def receive_receipt(
    payload: ReceiptPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Channel service calls this endpoint with delivery updates.
    We update the message status and campaign counters.
    """
    result = await db.execute(
        select(Message).where(Message.id == uuid.UUID(payload.message_id))
    )
    message = result.scalar_one_or_none()
    if not message:
        return {"status": "message not found"}

    event = payload.event
    occurred_at = datetime.fromisoformat(payload.occurred_at)

    # Update message status + timestamp
    status_map = {
        "sent":      MessageStatus.sent,
        "delivered": MessageStatus.delivered,
        "opened":    MessageStatus.opened,
        "clicked":   MessageStatus.clicked,
        "failed":    MessageStatus.failed,
    }
    if event in status_map:
        message.status = status_map[event]
        setattr(message, f"{event}_at", occurred_at)

    # Log event to campaign_events table
    db.add(CampaignEvent(
        id=uuid.uuid4(),
        message_id=message.id,
        campaign_id=message.campaign_id,
        customer_id=message.customer_id,
        event_type=event,
        occurred_at=occurred_at,
    ))

    # Update campaign counters
    result2 = await db.execute(
        select(Campaign).where(Campaign.id == message.campaign_id)
    )
    campaign = result2.scalar_one_or_none()
    if campaign:
        counter_map = {
            "delivered": "total_delivered",
            "opened":    "total_opened",
            "clicked":   "total_clicked",
            "failed":    "total_failed",
        }
        if event in counter_map:
            current = getattr(campaign, counter_map[event]) or 0
            setattr(campaign, counter_map[event], current + 1)

    await db.commit()
    return {"status": "ok"}


def _campaign_to_response(c: Campaign) -> CampaignResponse:
    return CampaignResponse(
        id=str(c.id),
        name=c.name,
        segment_id=str(c.segment_id),
        channel=c.channel.value,
        message_template=c.message_template,
        status=c.status.value,
        total_sent=c.total_sent or 0,
        total_delivered=c.total_delivered or 0,
        total_opened=c.total_opened or 0,
        total_clicked=c.total_clicked or 0,
        total_failed=c.total_failed or 0,
        created_at=c.created_at,
    )