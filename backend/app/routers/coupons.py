import random
import string
import httpx
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, text
from app.database import get_session
from app.core.config import settings
from app.core.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter()

SHOPIFY_DOMAIN = "happy-lapiz.myshopify.com"
SHOPIFY_TOKEN  = settings.SHOPIFY_ACCESS_TOKEN if hasattr(settings, "SHOPIFY_ACCESS_TOKEN") else ""
SHOPIFY_API    = f"https://{SHOPIFY_DOMAIN}/admin/api/2024-10/graphql.json"


def _shopify_headers():
    return {"X-Shopify-Access-Token": SHOPIFY_TOKEN, "Content-Type": "application/json"}


def _random_code(prefix: str = "HL", length: int = 8) -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{suffix}"


class CouponCampaignCreate(BaseModel):
    name: str
    discount_type: str  # "percentage" | "fixed"
    discount_value: float
    min_purchase: float = 0
    prefix: str = "HL"
    expires_at: Optional[str] = None
    applies_to: str = "all"
    coupon_mode: str = "dynamic"   # "dynamic" | "static"
    static_code: Optional[str] = None  # only for static mode


class GenerateCouponRequest(BaseModel):
    coupon_campaign_id: int
    contact_email: str
    contact_id: Optional[int] = None
    campaign_id: Optional[int] = None


@router.post("/campaigns")
def create_coupon_campaign(
    body: CouponCampaignCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
):
    """Crea un grupo de descuento en Shopify y lo registra en nuestra BD."""
    expires_iso = body.expires_at or "2099-12-31T23:59:59Z"

    if body.discount_type == "percentage":
        customer_gets = {"value": {"percentage": body.discount_value / 100}, "items": {"all": True}}
    else:
        customer_gets = {
            "value": {"discountAmount": {"amount": str(body.discount_value), "appliesOnEachItem": False}},
            "items": {"all": True},
        }

    mutation = """
    mutation discountCodeBasicCreate($basicCodeDiscount: DiscountCodeBasicInput!) {
      discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
        codeDiscountNode { id }
        userErrors { field message }
      }
    }"""
    # For static coupons use the user-specified code; for dynamic use a random seed code
    initial_code = body.static_code.strip().upper() if body.coupon_mode == "static" and body.static_code else _random_code(body.prefix, 6)

    variables = {
        "basicCodeDiscount": {
            "title": body.name,
            "code": initial_code,
            "startsAt": datetime.now(timezone.utc).isoformat(),
            "endsAt": expires_iso,
            "customerSelection": {"all": True},
            "customerGets": customer_gets,
            "appliesOncePerCustomer": True,
            "minimumRequirement": {
                "subtotal": {"greaterThanOrEqualToSubtotal": str(body.min_purchase)}
            } if body.min_purchase > 0 else None,
        }
    }

    shopify_id = None
    if SHOPIFY_TOKEN:
        try:
            resp = httpx.post(SHOPIFY_API, json={"query": mutation, "variables": variables},
                              headers=_shopify_headers(), timeout=10)
            data = resp.json()
            node = data.get("data", {}).get("discountCodeBasicCreate", {}).get("codeDiscountNode")
            if node:
                shopify_id = node["id"]
        except Exception:
            pass  # Save locally even if Shopify fails

    # Ensure new columns exist (idempotent — safe to run on every create)
    for col_sql in [
        "ALTER TABLE coupon_campaigns ADD COLUMN IF NOT EXISTS coupon_mode VARCHAR NOT NULL DEFAULT 'dynamic'",
        "ALTER TABLE coupon_campaigns ADD COLUMN IF NOT EXISTS static_code VARCHAR",
    ]:
        try:
            session.execute(text(col_sql))
            session.commit()
        except Exception:
            session.rollback()

    result = session.execute(text("""
        INSERT INTO coupon_campaigns (name, shopify_discount_id, discount_type, discount_value,
            min_purchase, prefix, expires_at, applies_to, coupon_mode, static_code, created_by)
        VALUES (:name, :sid, :dtype, :dval, :minp, :prefix, :exp, :applies, :mode, :scode, :uid)
        RETURNING id, name, discount_type, discount_value, prefix, coupon_mode, static_code
    """), {
        "name": body.name, "sid": shopify_id, "dtype": body.discount_type,
        "dval": body.discount_value, "minp": body.min_purchase, "prefix": body.prefix,
        "exp": expires_iso, "applies": body.applies_to, "uid": current_user.id,
        "mode": body.coupon_mode,
        "scode": initial_code if body.coupon_mode == "static" else None,
    }).fetchone()
    session.commit()
    return {
        "id": result[0], "name": result[1], "discount_type": result[2],
        "discount_value": result[3], "prefix": result[4],
        "coupon_mode": result[5], "static_code": result[6],
        "shopify_id": shopify_id,
    }


@router.get("/campaigns")
def list_coupon_campaigns(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    # Try full query with new columns; fall back to basic query if columns don't exist yet
    try:
        rows = session.execute(text("""
            SELECT id, name, discount_type, discount_value, prefix, expires_at, status, created_at,
                   (SELECT COUNT(*) FROM coupon_sends WHERE coupon_campaign_id = cc.id) as codes_sent,
                   COALESCE(coupon_mode, 'dynamic') as coupon_mode,
                   static_code
            FROM coupon_campaigns cc ORDER BY created_at DESC
        """)).fetchall()
    except Exception:
        session.rollback()
        rows = session.execute(text("""
            SELECT id, name, discount_type, discount_value, prefix, expires_at, status, created_at,
                   (SELECT COUNT(*) FROM coupon_sends WHERE coupon_campaign_id = cc.id) as codes_sent
            FROM coupon_campaigns cc ORDER BY created_at DESC
        """)).fetchall()
        return [{"id": r[0], "name": r[1], "discount_type": r[2], "discount_value": float(r[3]),
                 "prefix": r[4], "expires_at": r[5], "status": r[6], "created_at": r[7],
                 "codes_sent": r[8], "coupon_mode": "dynamic", "static_code": None} for r in rows]
    return [{"id": r[0], "name": r[1], "discount_type": r[2], "discount_value": float(r[3]),
             "prefix": r[4], "expires_at": r[5], "status": r[6], "created_at": r[7],
             "codes_sent": r[8], "coupon_mode": r[9], "static_code": r[10]} for r in rows]


@router.post("/generate")
def generate_coupon(
    body: GenerateCouponRequest,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """Genera un código único para un contacto. Si ya tiene uno en esta campaña, lo retorna."""
    existing = session.exec(text("""
        SELECT code FROM coupon_sends
        WHERE coupon_campaign_id = :cid AND contact_email = :email
        LIMIT 1
    """), {"cid": body.coupon_campaign_id, "email": body.contact_email.lower()}).fetchone()

    if existing:
        return {"code": existing[0], "new": False}

    campaign = session.exec(text(
        "SELECT prefix, discount_type, discount_value, expires_at FROM coupon_campaigns WHERE id = :id"
    ), {"id": body.coupon_campaign_id}).fetchone()

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña de cupón no encontrada")

    prefix, dtype, dval, expires_at = campaign

    # Generate unique code
    for _ in range(10):
        code = _random_code(prefix, 8)
        exists = session.exec(text("SELECT 1 FROM coupon_sends WHERE code = :c"), {"c": code}).fetchone()
        if not exists:
            break

    # Create in Shopify if token available
    shopify_code_id = None
    if SHOPIFY_TOKEN:
        try:
            # Get parent discount ID
            parent = session.exec(text(
                "SELECT shopify_discount_id FROM coupon_campaigns WHERE id = :id"
            ), {"id": body.coupon_campaign_id}).fetchone()

            if parent and parent[0]:
                mutation = """
                mutation discountRedeemCodeBulkAdd($discountId: ID!, $codes: [DiscountRedeemCodeInput!]!) {
                  discountRedeemCodeBulkAdd(discountId: $discountId, codes: $codes) {
                    bulkCreation { id }
                    userErrors { field message }
                  }
                }"""
                resp = httpx.post(SHOPIFY_API,
                    json={"query": mutation, "variables": {
                        "discountId": parent[0],
                        "codes": [{"code": code}]
                    }},
                    headers=_shopify_headers(), timeout=10)
        except Exception:
            pass

    session.exec(text("""
        INSERT INTO coupon_sends (coupon_campaign_id, contact_id, contact_email, code, shopify_code_id, campaign_id)
        VALUES (:ccamp, :cid, :email, :code, :scid, :camp)
    """), {
        "ccamp": body.coupon_campaign_id, "cid": body.contact_id,
        "email": body.contact_email.lower(), "code": code,
        "scid": shopify_code_id, "camp": body.campaign_id,
    })
    session.commit()
    return {"code": code, "new": True}


@router.get("/sends")
def list_coupon_sends(
    campaign_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    where = "WHERE cs.coupon_campaign_id = :cid" if campaign_id else ""
    rows = session.exec(text(f"""
        SELECT cs.code, cs.contact_email, cs.used, cs.created_at, cc.name, cc.discount_value, cc.discount_type
        FROM coupon_sends cs
        JOIN coupon_campaigns cc ON cc.id = cs.coupon_campaign_id
        {where}
        ORDER BY cs.created_at DESC LIMIT 200
    """), {"cid": campaign_id} if campaign_id else {}).all()
    return [{"code": r[0], "email": r[1], "used": r[2], "created_at": r[3],
             "campaign": r[4], "value": float(r[5]), "type": r[6]} for r in rows]
