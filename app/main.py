from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import wallet
from app.api.routes import user, api_key

from app.models.blacklist import BlacklistedToken
from app.models.user import User
from app.models.api_key import APIKey
from app.models.refresh_token import RefreshToken
from app.models.wallet import Wallet, Transaction


app = FastAPI(title="Micro-SaaS API Backend")

cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    user.router,
    prefix="/api/users",
    tags=["Users"],
)

app.include_router(
    api_key.router,
    prefix="/api/keys",
    tags=["API Keys"],
)

app.include_router(
    wallet.router,
    prefix="/api",
    tags=["Wallet"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to Micro-SaaS API!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
