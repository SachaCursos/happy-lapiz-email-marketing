from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    RESEND_API_KEY: str
    RESEND_FROM_EMAIL: str = "Happy Lápiz <hola@happylapiz.cl>"
    RESEND_WEBHOOK_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    # Public URL of THIS backend — used in embed.js to point the form submit call
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    # Si los datos fuente están en otra DB, ponla aquí; si no, usa la misma DATABASE_URL
    HOTBOAT_DATABASE_URL: str = ""
    NOTIFY_EMAIL: str = ""
    SHOPIFY_ACCESS_TOKEN: str = ""
    SHOPIFY_DOMAIN: str = "happy-lapiz.myshopify.com"

    class Config:
        env_file = ".env"


settings = Settings()
