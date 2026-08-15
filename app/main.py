from fastapi import FastAPI
from app.db.session import engine, Base
from app.models.blacklist import BlacklistedToken

from app.models.user import User
from app.models.api_key import APIKey

# Yahan maine api_keys se 's' hata diya hai
from app.api.routes import user, api_key

app = FastAPI(title="Micro-SaaS API Backend")

# Database tables create karna
Base.metadata.create_all(bind=engine)

# Routers connect karna (Yahan bhi api_key.router kar diya hai)
app.include_router(user.router, prefix="/api/users", tags=["Users"])
app.include_router(api_key.router, prefix="/api/keys", tags=["API Keys"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Micro-SaaS API!"}