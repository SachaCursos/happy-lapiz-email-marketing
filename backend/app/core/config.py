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
    NOTIFY_EMAIL: str = ""
    # When set (staging only), every outgoing email is redirected here instead
    # of the real recipient, with the original recipient tagged in the subject.
    EMAIL_OVERRIDE_TO: str = ""
    # Legacy single-tenant Happy Lápiz token — only used as an input to the
    # one-time bootstrap Shop migration. Runtime code should resolve
    # per-shop credentials via app.services.shopify_client instead.
    SHOPIFY_ACCESS_TOKEN: str = ""
    SHOPIFY_DOMAIN: str = "happy-lapiz.myshopify.com"

    # Multi-tenant Shopify OAuth app
    SHOPIFY_API_KEY: str = ""
    SHOPIFY_API_SECRET: str = ""
    SHOPIFY_SCOPES: str = "read_customers,read_orders,read_products,write_discounts,write_files,write_script_tags"
    SHOPIFY_TOKEN_ENCRYPTION_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
