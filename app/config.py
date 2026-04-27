import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.urandom(24)
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
    GOOGLE_USER = os.getenv("GOOGLE_USER")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/evoting_db")
    JWT_SECRET = os.getenv("JWT_SECRET", "edu-vote-jwt-secret-key-123")
