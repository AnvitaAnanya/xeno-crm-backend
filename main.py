from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import segments, campaigns, chat

app = FastAPI(title="Xeno Mini CRM", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(segments.router)
app.include_router(campaigns.router)
app.include_router(chat.router)

# Handle both with and without trailing slash
app.include_router(segments.router, prefix="")
app.include_router(campaigns.router, prefix="")
app.include_router(chat.router, prefix="")

@app.get("/")
async def root():
    return {"status": "CRM backend running"}