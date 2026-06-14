from google import genai
from google.genai import types
import json
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import Customer, Order, Campaign, Segment, Message
from app.services.segmentation import create_segment, get_segment_customers
from datetime import datetime, timedelta

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Tool definitions (Gemini format) ---

TOOLS = [
    {
        "name": "get_customer_stats",
        "description": "Get overall statistics about the customer base — total customers, revenue, breakdown by segment type.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "create_segment_and_preview",
        "description": "Create a customer segment based on filters and preview how many customers match.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Segment name"},
                "description": {"type": "string", "description": "What this segment represents"},
                "filters": {
                    "type": "object",
                    "description": "Filter rules: inactive_days, active_days, min_spend, max_spend, min_orders, city, preferred_channel"
                }
            },
            "required": ["name", "description", "filters"]
        }
    },
    {
        "name": "create_and_launch_campaign",
        "description": "Create and launch a campaign. Only call after marketer explicitly confirms.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Campaign name"},
                "segment_id": {"type": "string", "description": "Segment ID to target"},
                "channel": {
                    "type": "string",
                    "enum": ["whatsapp", "sms", "email", "rcs"],
                    "description": "Channel to send on"
                },
                "message_template": {
                    "type": "string",
                    "description": "Message text with {{name}}, {{city}}, {{total_spend}} placeholders"
                }
            },
            "required": ["name", "segment_id", "channel", "message_template"]
        }
    },
    {
        "name": "get_campaign_performance",
        "description": "Get performance stats for recent campaigns.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of campaigns to fetch"}
            }
        }
    },
    {
        "name": "list_segments",
        "description": "List all saved segments with customer counts.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]

SYSTEM_PROMPT = """You are an AI assistant for a fashion brand's CRM called Xeno.
You help marketers reach their shoppers intelligently.

You have access to real customer data and MUST use your tools to take action.

CRITICAL RULES:
- When asked to re-engage, win-back, or target any customer group — IMMEDIATELY call create_segment_and_preview. Do not describe what you will do, just do it.
- When asked about customers or stats — IMMEDIATELY call get_customer_stats.
- When asked about campaigns — IMMEDIATELY call get_campaign_performance.
- NEVER respond with a plan of what you will do. Always call the tool first, then explain what you did.
- After creating a segment, always draft a message and ask for confirmation to send.
- Only call create_and_launch_campaign after the marketer says yes/confirm/send/go ahead.

Your personality: confident, data-driven, action-oriented. You do first, explain after.

Message placeholders available: {{name}}, {{city}}, {{total_spend}}
Format responses in clear, scannable markdown.
"""


# --- Tool execution (identical to before) ---

async def execute_tool(tool_name: str, tool_input: dict, db: AsyncSession) -> dict:

    if tool_name == "get_customer_stats":
        total = await db.execute(select(func.count(Customer.id)))
        total_customers = total.scalar()

        total_rev = await db.execute(select(func.sum(Customer.total_spend)))
        total_revenue = total_rev.scalar() or 0

        cutoff_60 = datetime.utcnow() - timedelta(days=60)
        cutoff_30 = datetime.utcnow() - timedelta(days=30)
        cutoff_14 = datetime.utcnow() - timedelta(days=14)

        lapsed = await db.execute(
            select(func.count(Customer.id)).where(Customer.last_order_date <= cutoff_60)
        )
        active = await db.execute(
            select(func.count(Customer.id)).where(Customer.last_order_date >= cutoff_30)
        )
        new_customers = await db.execute(
            select(func.count(Customer.id)).where(Customer.last_order_date >= cutoff_14)
        )
        vip = await db.execute(
            select(func.count(Customer.id)).where(Customer.total_spend >= 20000)
        )

        return {
            "total_customers": total_customers,
            "total_revenue": round(total_revenue, 2),
            "lapsed_60_days": lapsed.scalar(),
            "active_last_30_days": active.scalar(),
            "new_last_14_days": new_customers.scalar(),
            "vip_spend_above_20k": vip.scalar(),
        }

    elif tool_name == "create_segment_and_preview":
        segment = await create_segment(
            name=tool_input["name"],
            description=tool_input["description"],
            filters=tool_input["filters"],
            db=db
        )
        customers = await get_segment_customers(segment.filters, db)
        sample = [
            {"name": c.name, "city": c.city, "total_spend": c.total_spend}
            for c in customers[:3]
        ]
        return {
            "segment_id": str(segment.id),
            "segment_name": segment.name,
            "customer_count": segment.customer_count,
            "sample_customers": sample,
            "filters_applied": segment.filters
        }

    elif tool_name == "create_and_launch_campaign":
        from app.services.campaign_service import launch_campaign
        import uuid as _uuid

        campaign = Campaign(
            id=_uuid.uuid4(),
            name=tool_input["name"],
            segment_id=_uuid.UUID(tool_input["segment_id"]),
            channel=tool_input["channel"],
            message_template=tool_input["message_template"],
            status="draft",
            total_sent=0,
            total_delivered=0,
            total_opened=0,
            total_clicked=0,
            total_failed=0,
        )
        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)

        import asyncio
        asyncio.create_task(launch_campaign(str(campaign.id), db))

        return {
            "campaign_id": str(campaign.id),
            "campaign_name": campaign.name,
            "status": "launching",
            "channel": tool_input["channel"],
            "message_preview": tool_input["message_template"]
        }

    elif tool_name == "get_campaign_performance":
        limit = tool_input.get("limit", 5)
        result = await db.execute(
            select(Campaign).order_by(Campaign.created_at.desc()).limit(limit)
        )
        campaigns = result.scalars().all()
        return {
            "campaigns": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "channel": c.channel.value,
                    "sent": c.total_sent or 0,
                    "delivered": c.total_delivered or 0,
                    "opened": c.total_opened or 0,
                    "clicked": c.total_clicked or 0,
                    "failed": c.total_failed or 0,
                    "delivery_rate": f"{round((c.total_delivered or 0) / max(c.total_sent or 1, 1) * 100)}%",
                    "open_rate": f"{round((c.total_opened or 0) / max(c.total_sent or 1, 1) * 100)}%",
                }
                for c in campaigns
            ]
        }

    elif tool_name == "list_segments":
        result = await db.execute(select(Segment).order_by(Segment.created_at.desc()))
        segments = result.scalars().all()
        return {
            "segments": [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "description": s.description,
                    "customer_count": s.customer_count,
                    "filters": s.filters
                }
                for s in segments
            ]
        }

    return {"error": f"Unknown tool: {tool_name}"}


# --- Main chat function ---

async def chat_with_ai(messages: list[dict], db: AsyncSession) -> dict:

    # Convert our messages to Gemini format
    gemini_contents = []
    for msg in messages:
        gemini_contents.append(
            types.Content(
                role="user" if msg["role"] == "user" else "model",
                parts=[types.Part(text=msg["content"])]
            )
        )

    tool_config = types.Tool(function_declarations=[
        types.FunctionDeclaration(**t) for t in TOOLS
    ])

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=gemini_contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[tool_config],
        )
    )

    tool_results_data = []

    # Handle tool calls in a loop
    while (
        response.candidates and
        response.candidates[0].content.parts and
        getattr(response.candidates[0].content.parts[0], 'function_call', None) is not None
    ):

        part = response.candidates[0].content.parts[0]
        tool_name = part.function_call.name
        tool_input = dict(part.function_call.args)

        result = await execute_tool(tool_name, tool_input, db)
        tool_results_data.append({"tool": tool_name, "result": result})

        # Add assistant response + tool result to history
        gemini_contents.append(response.candidates[0].content)
        gemini_contents.append(
            types.Content(
                role="user",
                parts=[types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response={"result": result}
                    )
                )]
            )
        )

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=gemini_contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[tool_config],
            )
        )

    # Extract final text
    final_text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            final_text = part.text
            break

    return {
        "response": final_text,
        "tool_calls": tool_results_data
    }