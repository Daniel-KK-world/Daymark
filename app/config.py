import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.secret_key = os.getenv("SECRET_KEY", "change-me")
        self.algorithm = os.getenv("ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

settings = Settings()