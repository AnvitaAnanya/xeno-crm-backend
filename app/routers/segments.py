from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.models import Segment, Customer
from app.services.segmentation import (
    create_segment, get_segment_customers
)
import uuid

router = APIRouter(prefix="/segments", tags=["segments"])


# --- Request/Response schemas ---

class SegmentCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    filters: dict


class SegmentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    filters: dict
    customer_count: int

    class Config:
        from_attributes = True


class CustomerPreview(BaseModel):
    id: str
    name: str
    email: str
    city: Optional[str]
    total_spend: float
    order_count: int
    preferred_channel: str

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.post("/", response_model=SegmentResponse)
async def create_new_segment(
    payload: SegmentCreate,
    db: AsyncSession = Depends(get_db)
):
    segment = await create_segment(
        name=payload.name,
        description=payload.description,
        filters=payload.filters,
        db=db
    )
    return SegmentResponse(
        id=str(segment.id),
        name=segment.name,
        description=segment.description,
        filters=segment.filters,
        customer_count=segment.customer_count
    )


@router.get("/", response_model=list[SegmentResponse])
async def list_segments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Segment).order_by(Segment.created_at.desc()))
    segments = result.scalars().all()
    return [
        SegmentResponse(
            id=str(s.id),
            name=s.name,
            description=s.description,
            filters=s.filters,
            customer_count=s.customer_count
        )
        for s in segments
    ]


@router.get("/{segment_id}/customers", response_model=list[CustomerPreview])
async def preview_segment_customers(
    segment_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Segment).where(Segment.id == uuid.UUID(segment_id))
    )
    segment = result.scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    customers = await get_segment_customers(segment.filters, db)
    return [
        CustomerPreview(
            id=str(c.id),
            name=c.name,
            email=c.email,
            city=c.city,
            total_spend=c.total_spend,
            order_count=c.order_count,
            preferred_channel=c.preferred_channel.value
        )
        for c in customers
    ]