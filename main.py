from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.routers import segments, campaigns, chat

app = FastAPI(title="Xeno Mini CRM", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_trailing_slash(request: Request, call_next):
    path = request.url.path
    if not path.endswith("/") and "." not in path:
        return RedirectResponse(
            url=str(request.url).replace(path, path + "/"),
            status_code=308   # 308 preserves POST method unlike 307
        )
    return await call_next(request)

app.include_router(segments.router)
app.include_router(campaigns.router)
app.include_router(chat.router)

@app.get("/")
async def root():
    return {"status": "CRM backend running"}