from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.database import create_db_and_tables
from app.routers import auth, contacts, segments, templates, campaigns, webhooks, analytics, sync, automations, forms, admin, coupons

app = FastAPI(title="Happy Lápiz Email Marketing API", version="1.0.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    # "*" needed so embed.js can submit forms from any website (e.g. hotboat.cl).
    # Auth-protected routes still require a Bearer token, so this is safe.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["contacts"])
app.include_router(segments.router, prefix="/api/segments", tags=["segments"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(automations.router, prefix="/api/automations", tags=["automations"])
app.include_router(forms.router, prefix="/api/forms", tags=["forms"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(coupons.router, prefix="/api/coupons", tags=["coupons"])


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    from app.services.automation_engine import start_scheduler
    start_scheduler()


@app.get("/api/health")
def health():
    return {"status": "ok"}
