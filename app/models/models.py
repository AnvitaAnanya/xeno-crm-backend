from sqlalchemy import (
    Column, String, Integer, Float, DateTime, 
    ForeignKey, JSON, Text, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid
import enum

Base = declarative_base()

# --- Enums (fixed set of allowed values) ---

class ChannelType(str, enum.Enum):
    whatsapp = "whatsapp"
    sms = "sms"
    email = "email"
    rcs = "rcs"

class CampaignStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    completed = "completed"
    failed = "failed"

class MessageStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    clicked = "clicked"
    failed = "failed"

# --- Tables ---

class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    city = Column(String)
    preferred_channel = Column(Enum(ChannelType), default=ChannelType.whatsapp)
    total_spend = Column(Float, default=0.0)
    order_count = Column(Integer, default=0)
    last_order_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="customer")
    messages = relationship("Message", back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    amount = Column(Float, nullable=False)
    items = Column(JSON)             # e.g. [{"name": "Blue Kurta", "qty": 2}]
    ordered_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")


class Segment(Base):
    __tablename__ = "segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    filters = Column(JSON, nullable=False)   # the rule set as JSON
    customer_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    campaigns = relationship("Campaign", back_populates="segment")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    segment_id = Column(UUID(as_uuid=True), ForeignKey("segments.id"))
    channel = Column(Enum(ChannelType), nullable=False)
    message_template = Column(Text, nullable=False)
    status = Column(Enum(CampaignStatus), default=CampaignStatus.draft)
    
    # stats — denormalised for fast reads
    total_sent = Column(Integer, default=0)
    total_delivered = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    segment = relationship("Segment", back_populates="campaigns")
    messages = relationship("Message", back_populates="campaign")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"))
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    channel = Column(Enum(ChannelType), nullable=False)
    content = Column(Text, nullable=False)   # personalised message text
    status = Column(Enum(MessageStatus), default=MessageStatus.queued)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="messages")
    customer = relationship("Customer", back_populates="messages")
    events = relationship("CampaignEvent", back_populates="message")


class CampaignEvent(Base):
    __tablename__ = "campaign_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"))
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"))
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    event_type = Column(String, nullable=False)
    occurred_at = Column(DateTime, default=datetime.utcnow)
    event_metadata = Column(JSON, nullable=True)        # ← renamed from metadata

    message = relationship("Message", back_populates="events")