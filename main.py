from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import segments, campaigns, chat

app = FastAPI(title="Xeno Mini CRM", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://xeno-crm-frontend-website.vercel.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(segments.router)
app.include_router(campaigns.router)
app.include_router(chat.router)

@app.get("/")
async def root():
    return {"status": "CRM backend running"}