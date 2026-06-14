from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import segments, campaigns, chat

app = FastAPI(title="Xeno Mini CRM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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