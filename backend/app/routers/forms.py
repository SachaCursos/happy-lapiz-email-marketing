import json
import random
import string
import textwrap
from datetime import datetime
from typing import List
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select
from sqlalchemy import text

from app.core.config import settings
from app.core.deps import get_current_user, require_editor
from app.database import get_session
from app.models.automation import AutomationEnrollment
from app.models.contact import Contact
from app.models.form import (
    FormSubmission, FormSubmitPayload,
    SignupForm, SignupFormCreate, SignupFormRead, SignupFormUpdate,
)
from app.models.gift_recipient import GiftRecipient, GiftRecipientCreate, GiftRecipientRead, RELACION_OPTIONS
from app.models.user import User

router = APIRouter()


# ── Authenticated CRUD ────────────────────────────────────────────────────────

@router.get("", response_model=List[SignupFormRead])
def list_forms(session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    return session.exec(select(SignupForm).order_by(SignupForm.created_at.desc())).all()


@router.post("", response_model=SignupFormRead, status_code=201)
def create_form(
    payload: SignupFormCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_editor),
):
    form = SignupForm(**payload.model_dump(), created_by=current_user.id)
    session.add(form)
    session.commit()
    session.refresh(form)
    return form


@router.get("/{form_id}", response_model=SignupFormRead)
def get_form(form_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)):
    f = session.get(SignupForm, form_id)
    if not f:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    return f


@router.patch("/{form_id}", response_model=SignupFormRead)
def update_form(
    form_id: int,
    payload: SignupFormUpdate,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    f = session.get(SignupForm, form_id)
    if not f:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(f, k, v)
    f.updated_at = datetime.utcnow()
    session.add(f)
    session.commit()
    session.refresh(f)
    return f


@router.delete("/{form_id}", status_code=204)
def delete_form(
    form_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
):
    f = session.get(SignupForm, form_id)
    if not f:
        raise HTTPException(status_code=404, detail="Formulario no encontrado")
    session.delete(f)
    session.commit()


@router.get("/{form_id}/ab-stats")
def form_ab_stats(
    form_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    rows = session.execute(text("""
        SELECT ab_variant, COUNT(*) as total
        FROM form_submissions
        WHERE form_id = :fid AND ab_variant IS NOT NULL
        GROUP BY ab_variant
        ORDER BY ab_variant
    """), {"fid": form_id}).fetchall()
    total_all = session.execute(text(
        "SELECT COUNT(*) FROM form_submissions WHERE form_id = :fid"
    ), {"fid": form_id}).scalar() or 0
    return {
        "total": total_all,
        "variants": [{"variant_id": r[0], "submissions": r[1]} for r in rows],
    }


@router.get("/{form_id}/submissions")
def list_submissions(
    form_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    subs = session.exec(
        select(FormSubmission)
        .where(FormSubmission.form_id == form_id)
        .order_by(FormSubmission.created_at.desc())
        .limit(200)
    ).all()
    all_subs = session.exec(
        select(FormSubmission).where(FormSubmission.form_id == form_id)
    ).all()
    return {"total": len(all_subs), "submissions": subs}


# ── Public endpoints (no auth) ────────────────────────────────────────────────

def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


@router.options("/{form_id}/submit")
def submit_preflight(form_id: int):
    return Response(status_code=204, headers=_cors_headers())


def _generate_dynamic_coupon(session: Session, coupon_campaign_id: int, email: str) -> str | None:
    """Generate a unique Shopify coupon code for a form submission. Returns code or None on failure."""
    existing = session.execute(text(
        "SELECT code FROM coupon_sends WHERE coupon_campaign_id = :cid AND contact_email = :email LIMIT 1"
    ), {"cid": coupon_campaign_id, "email": email.lower()}).fetchone()
    if existing:
        return existing[0]

    campaign = session.execute(text(
        "SELECT prefix, discount_type, discount_value, shopify_discount_id FROM coupon_campaigns WHERE id = :id"
    ), {"id": coupon_campaign_id}).fetchone()
    if not campaign:
        return None

    prefix = campaign[0] or "HL"
    shopify_id = campaign[3]

    for _ in range(10):
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        code = f"{prefix}-{suffix}"
        dup = session.execute(text("SELECT 1 FROM coupon_sends WHERE code = :c"), {"c": code}).fetchone()
        if not dup:
            break

    if settings.SHOPIFY_ACCESS_TOKEN and shopify_id:
        try:
            mutation = """
            mutation discountRedeemCodeBulkAdd($discountId: ID!, $codes: [DiscountRedeemCodeInput!]!) {
              discountRedeemCodeBulkAdd(discountId: $discountId, codes: $codes) {
                bulkCreation { id }
                userErrors { field message }
              }
            }"""
            httpx.post(
                f"https://{settings.SHOPIFY_DOMAIN}/admin/api/2024-10/graphql.json",
                json={"query": mutation, "variables": {"discountId": shopify_id, "codes": [{"code": code}]}},
                headers={"X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN, "Content-Type": "application/json"},
                timeout=8,
            )
        except Exception:
            pass

    session.execute(text("""
        INSERT INTO coupon_sends (coupon_campaign_id, contact_email, code)
        VALUES (:ccamp, :email, :code)
        ON CONFLICT DO NOTHING
    """), {"ccamp": coupon_campaign_id, "email": email.lower(), "code": code})
    return code


@router.post("/{form_id}/submit")
def submit_form(
    form_id: int,
    payload: FormSubmitPayload,
    response: Response,
    session: Session = Depends(get_session),
):
    for k, v in _cors_headers().items():
        response.headers[k] = v

    f = session.get(SignupForm, form_id)
    if not f or f.status != "active":
        raise HTTPException(status_code=404, detail="Formulario no disponible")

    email = payload.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")

    origin = payload.source_url or f"Formulario #{form_id}"

    contact = session.exec(select(Contact).where(Contact.email == email)).first()
    if contact:
        if not contact.opted_in:
            contact.opted_in = True
            contact.opted_in_at = datetime.utcnow()
            contact.opted_out_at = None
        if payload.name and not contact.name:
            contact.name = payload.name.strip() or None
        if payload.phone and not contact.phone:
            contact.phone = payload.phone.strip() or None
        if not contact.origin_utm:
            contact.origin_utm = origin
        contact.updated_at = datetime.utcnow()
        session.add(contact)
    else:
        contact = Contact(
            email=email,
            name=(payload.name or "").strip() or None,
            phone=(payload.phone or "").strip() or None,
            origin_utm=origin,
            opted_in=True,
            opted_in_at=datetime.utcnow(),
        )
        session.add(contact)

    # Dynamic coupon generation
    coupon_code: str | None = None
    if f.coupon_campaign_id:
        coupon_code = _generate_dynamic_coupon(session, f.coupon_campaign_id, email)
    elif f.coupon_code:
        coupon_code = f.coupon_code

    session.add(FormSubmission(
        form_id=form_id,
        email=email,
        name=(payload.name or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        source_url=payload.source_url,
        extra_data=payload.extra_data or None,
        coupon_code=coupon_code,
        ab_variant=payload.ab_variant or None,
    ))
    session.commit()

    # Enroll in automation for coupon email if configured
    if f.coupon_automation_id and coupon_code:
        session.flush()
        existing_enrollment = session.exec(
            select(AutomationEnrollment).where(
                AutomationEnrollment.automation_id == f.coupon_automation_id,
                AutomationEnrollment.trigger_key == f"form_submitted:{form_id}:{email}",
            )
        ).first()
        if not existing_enrollment:
            from app.models.automation import Automation
            auto = session.get(Automation, f.coupon_automation_id)
            if auto and auto.status == "active":
                extra = {
                    "nombre": (payload.name or "").strip() or email,
                    "first_name": ((payload.name or "").strip() or email).split()[0],
                    "email": email,
                    "coupon_code": coupon_code,
                }
                from datetime import timedelta
                from app.services.automation_engine import _get_steps
                steps = _get_steps(auto)
                first_delay = float(steps[0].get("delay_hours", 0)) if steps else 0
                enrollment = AutomationEnrollment(
                    automation_id=f.coupon_automation_id,
                    contact_email=email,
                    trigger_key=f"form_submitted:{form_id}:{email}",
                    enrolled_at=datetime.utcnow(),
                    next_send_at=datetime.utcnow() + timedelta(hours=first_delay),
                    next_step=1,
                    status="active",
                    extra_vars_json=json.dumps(extra),
                )
                session.add(enrollment)
                session.commit()

    return {"ok": True, "coupon_code": coupon_code}


@router.get("/{form_id}/embed.js", response_class=PlainTextResponse)
def embed_js(form_id: int, session: Session = Depends(get_session)):
    f = session.get(SignupForm, form_id)
    if not f or f.status != "active":
        return PlainTextResponse("/* form not found */", media_type="application/javascript")

    cfg = {
        "id": f.id,
        "title": f.title,
        "description": f.description or "",
        "button_text": f.button_text,
        "success_message": f.success_message,
        "collect_name": f.collect_name,
        "collect_phone": f.collect_phone,
        "custom_fields": f.custom_form_fields or [],
        "trigger": f.popup_trigger,
        "delay_seconds": f.popup_delay_seconds,
        "scroll_pct": f.popup_scroll_pct,
        "html_override": f.html_override or "",
        "coupon_code": f.coupon_code or "",
        "has_dynamic_coupon": bool(f.coupon_campaign_id),
        "design": f.design_config or {},
        "steps": f.steps_config or [],
        "ab_variants": f.ab_variants or [],
        "api": settings.BACKEND_PUBLIC_URL,
    }

    js = _build_embed_js(cfg)
    return PlainTextResponse(
        js,
        media_type="application/javascript",
        headers={**_cors_headers(), "Cache-Control": "public, max-age=60"},
    )


# ── Tracking pixel ───────────────────────────────────────────────────────────

@router.get("/track.js", response_class=PlainTextResponse)
def tracking_pixel():
    """
    Script de tracking universal para happylapiz.cl.
    Pégalo en Shopify → Configuración → Checkout → Scripts adicionales,
    o en el <head> del tema.

    Trackea:
      - viewed_product  → cuando alguien ve una página de producto
      - active_on_site  → cuando el email del cliente está disponible (logged in)
      - added_to_cart   → cuando Shopify dispara el evento cart:add
    """
    api = settings.BACKEND_PUBLIC_URL
    js = f"""(function(){{
  var API='{api}/api/shopify/track';
  function getEmail(){{
    // Shopify expone el email del cliente logueado en window.ShopifyAnalytics
    try{{
      return (window.ShopifyAnalytics&&window.ShopifyAnalytics.meta&&window.ShopifyAnalytics.meta.email)||
             (window.__st&&window.__st.cid?null:null)||'';
    }}catch(e){{return '';}}
  }}
  function send(evt,extra){{
    var email=getEmail();
    var payload=Object.assign({{event:evt,email:email,url:location.href}},extra||{{}});
    fetch(API,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload),keepalive:true}}).catch(function(){{}});
  }}
  // Viewed Product
  if(window.ShopifyAnalytics&&ShopifyAnalytics.meta&&ShopifyAnalytics.meta.product){{
    var p=ShopifyAnalytics.meta.product;
    send('viewed_product',{{product_id:String(p.id||''),product_title:p.title||''}});
  }}
  // Active on site (email available)
  var email=getEmail();
  if(email){{
    send('active_on_site',{{}});
  }}
  // Added to cart (Shopify theme event)
  document.addEventListener('cart:add',function(e){{
    var item=(e.detail&&e.detail.cart&&e.detail.cart.items&&e.detail.cart.items[0])||{{}};
    send('added_to_cart',{{product_id:String(item.product_id||''),product_title:item.title||'',url:location.href}});
  }});
  // Fallback: listen to fetch/XHR for /cart/add
  var origFetch=window.fetch;
  window.fetch=function(input,init){{
    var url=typeof input==='string'?input:(input&&input.url)||'';
    if(url.indexOf('/cart/add')!==-1){{
      setTimeout(function(){{send('added_to_cart',{{url:location.href}});}},500);
    }}
    return origFetch.apply(this,arguments);
  }};
}})();
"""
    return PlainTextResponse(js, media_type="application/javascript",
                             headers={**_cors_headers(), "Cache-Control": "public, max-age=3600"})


# ── Embed JS builder ──────────────────────────────────────────────────────────

def _build_embed_js(cfg: dict) -> str:
    cfg_json = json.dumps(cfg, ensure_ascii=False)
    d = cfg.get("design", {})

    header_bg   = d.get("header_bg", "#0369a1")
    header_bg2  = d.get("header_bg2", "#0ea5e9")
    header_text = d.get("header_text", "#ffffff")
    body_bg     = d.get("body_bg", "#ffffff")
    btn_bg      = d.get("btn_bg", "#0369a1")
    btn_bg2     = d.get("btn_bg2", "#0ea5e9")
    btn_text    = d.get("btn_text", "#ffffff")
    input_bdr   = d.get("input_border", "#e2e8f0")
    radius      = int(d.get("border_radius", 16))
    font        = d.get("font", "system-ui")

    return textwrap.dedent(f"""
    (function() {{
      var C = {cfg_json};
      var STORE_KEY = 'hb_form_' + C.id;
      // localStorage/sessionStorage can throw in Safari private mode — wrap in try/catch
      var _ls = (function(){{ try {{ return localStorage; }} catch(e) {{ return {{getItem:function(){{return null;}},setItem:function(){{}}}}; }} }})();
      var _ss = (function(){{ try {{ return sessionStorage; }} catch(e) {{ return {{getItem:function(){{return null;}},setItem:function(){{}}}}; }} }})();
      // Never show again if already submitted
      if (_ls.getItem(STORE_KEY) === 'submitted') return;
      // Don't show again in this browser session if already dismissed
      if (_ss.getItem(STORE_KEY + '_d')) return;

      // ── A/B variant selection ─────────────────────────────────────────────
      var _abVariant = null;
      if (C.ab_variants && C.ab_variants.length >= 2) {{
        var _abKey = 'hb_ab_' + C.id;
        var _stored = _ss.getItem(_abKey);
        if (_stored) {{
          // Use previously assigned variant (consistent per session)
          for (var _i = 0; _i < C.ab_variants.length; _i++) {{
            if (String(C.ab_variants[_i].id) === _stored) {{ _abVariant = C.ab_variants[_i]; break; }}
          }}
        }}
        if (!_abVariant) {{
          var _total = 0;
          for (var _i = 0; _i < C.ab_variants.length; _i++) _total += parseFloat(C.ab_variants[_i].weight || 1);
          var _rand = Math.random() * _total, _cum = 0;
          for (var _i = 0; _i < C.ab_variants.length; _i++) {{
            _cum += parseFloat(C.ab_variants[_i].weight || 1);
            if (_rand <= _cum) {{ _abVariant = C.ab_variants[_i]; break; }}
          }}
          if (!_abVariant) _abVariant = C.ab_variants[C.ab_variants.length - 1];
          _ss.setItem(_abKey, String(_abVariant.id));
        }}
        // Override content with variant's values
        if (_abVariant.title)       C.title       = _abVariant.title;
        if (_abVariant.description) C.description = _abVariant.description;
        if (_abVariant.button_text) C.button_text = _abVariant.button_text;
      }}

      var D = C.design || {{}};
      var headerBg  = D.header_bg  || '{header_bg}';
      var headerBg2 = D.header_bg2 || '{header_bg2}';
      var headerTxt = D.header_text|| '{header_text}';
      var bodyBg    = D.body_bg    || '{body_bg}';
      var btnBg     = D.btn_bg     || '{btn_bg}';
      var btnBg2    = D.btn_bg2    || '{btn_bg2}';
      var btnTxt    = D.btn_text   || '{btn_text}';
      var inpBdr    = D.input_border|| '{input_bdr}';
      var radius    = (D.border_radius !== undefined ? D.border_radius : {radius}) + 'px';
      var fontFam   = D.font       || '{font}';

      // Load Google Font if needed
      var _gFonts = {{'Poppins':'Poppins:wght@400;600;700','Montserrat':'Montserrat:wght@400;600;700',"'Playfair Display'":"Playfair+Display:wght@400;700","'DM Sans'":"DM+Sans:wght@400;600"}};
      if (_gFonts[fontFam]) {{
        var _fl = document.createElement('link');
        _fl.rel = 'stylesheet';
        _fl.href = 'https://fonts.googleapis.com/css2?family=' + _gFonts[fontFam] + '&display=swap';
        document.head.appendChild(_fl);
      }}

      var STYLES = [
        '@keyframes hbSlideUp{{from{{transform:translateY(80px);opacity:0}}to{{transform:translateY(0);opacity:1}}}}',
        '@keyframes hbFadeIn{{from{{opacity:0;transform:scale(0.96)}}to{{opacity:1;transform:scale(1)}}}}',
        '#hb-popup-overlay{{position:fixed;bottom:0;left:0;right:0;display:flex;justify-content:center;padding:16px;z-index:2147483647;pointer-events:none;font-family:' + fontFam + ',system-ui,sans-serif;}}',
        '#hb-popup-overlay.hb-centered{{bottom:0;top:0;align-items:center;background:rgba(0,0,0,0.45);pointer-events:all;}}',
        '#hb-popup-box{{background:' + bodyBg + ';border-radius:' + radius + ';overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.2);max-width:440px;width:100%;max-height:90vh;overflow-y:auto;pointer-events:all;border:1px solid #e2e8f0;}}',
        '#hb-popup-overlay:not(.hb-centered) #hb-popup-box{{animation:hbSlideUp 0.4s cubic-bezier(0.34,1.56,0.64,1);}}',
        '#hb-popup-overlay.hb-centered #hb-popup-box{{animation:hbFadeIn 0.25s ease;}}',
        '#hb-popup-header{{background:linear-gradient(135deg,' + headerBg + ' 0%,' + headerBg2 + ' 100%);padding:20px 48px 20px 24px;position:relative;}}',
        '#hb-popup-close{{position:absolute;top:12px;right:12px;background:rgba(255,255,255,0.2);border:none;color:' + headerTxt + ';width:28px;height:28px;border-radius:50%;cursor:pointer;font-size:18px;line-height:28px;text-align:center;transition:background .2s;}}',
        '#hb-popup-close:hover{{background:rgba(255,255,255,0.35);}}',
        '#hb-popup-title{{margin:0;color:' + headerTxt + ';font-size:19px;font-weight:700;line-height:1.3;}}',
        '#hb-popup-subtitle{{margin:4px 0 0;color:' + headerTxt + ';opacity:0.8;font-size:13px;}}',
        '#hb-popup-body{{padding:20px 24px;background:' + bodyBg + ';}}',
        '#hb-popup-desc{{margin:0 0 16px;color:#64748b;font-size:14px;line-height:1.5;}}',
        '#hb-popup-progress{{display:flex;gap:4px;margin-bottom:16px;}}',
        '.hb-progress-dot{{flex:1;height:4px;border-radius:2px;background:#e2e8f0;transition:background .3s;}}',
        '.hb-progress-dot.hb-done{{background:' + btn_bg + ';}}',
        '.hb-step{{display:none;}}',
        '.hb-step.hb-active{{display:block;}}',
        '.hb-input{{width:100%;padding:10px 14px;border:1.5px solid ' + inpBdr + ';border-radius:8px;font-size:14px;color:#1e293b;margin-bottom:10px;box-sizing:border-box;outline:none;transition:border-color .2s;font-family:inherit;background:#fff;}}',
        '.hb-input:focus{{border-color:' + btn_bg + ';}}',
        '.hb-label{{display:block;font-size:12px;color:#64748b;margin-bottom:4px;}}',
        '#hb-popup-btn{{width:100%;padding:12px;background:linear-gradient(135deg,' + btnBg + ',' + btnBg2 + ');color:' + btnTxt + ';border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;transition:opacity .2s;margin-top:4px;font-family:inherit;}}',
        '#hb-popup-btn:hover{{opacity:0.88;}}',
        '#hb-popup-btn:disabled{{opacity:0.5;cursor:not-allowed;}}',
        '#hb-popup-success{{display:none;text-align:center;padding:8px 0 4px;}}',
        '.hb-coupon-box{{margin:4px 0 12px;padding:14px 20px;background:#f0f9ff;border:2px dashed ' + btn_bg + ';border-radius:12px;text-align:center;}}',
        '#hb-popup-fine{{margin:12px 0 0;color:#94a3b8;font-size:11px;text-align:center;}}',
      ].join('\\n');

      try {{
        var style = document.createElement('style');
        style.textContent = STYLES;
        (document.head || document.documentElement).appendChild(style);
      }} catch(e) {{}}

      // ── Debug indicator (shows embed.js loaded) ─────────────────────────────
      try {{
        var _dbg = document.createElement('div');
        _dbg.id = 'hb-debug-ok';
        _dbg.style.cssText = 'position:fixed;bottom:4px;right:4px;background:#16a34a;color:#fff;padding:4px 8px;font-size:11px;border-radius:4px;z-index:2147483647;font-family:sans-serif';
        _dbg.textContent = 'Popup OK';
        (document.body || document.documentElement).appendChild(_dbg);
        setTimeout(function(){{ if (_dbg.parentNode) _dbg.parentNode.removeChild(_dbg); }}, 5000);
      }} catch(e) {{}}

      // ── Field renderer ──────────────────────────────────────────────────────
      var CF_MAP = {{}};
      (C.custom_fields||[]).forEach(function(f){{ CF_MAP[f.key] = f; }});

      function renderField(key) {{
        var lbl, inp;
        if (key === 'email') {{
          lbl = '<label class="hb-label">Email *</label>';
          inp = '<input class="hb-input" type="email" name="email" placeholder="tu@email.com" required />';
        }} else if (key === 'name') {{
          lbl = '<label class="hb-label">Nombre</label>';
          inp = '<input class="hb-input" type="text" name="name" placeholder="Tu nombre" />';
        }} else if (key === 'phone') {{
          lbl = '<label class="hb-label">Teléfono</label>';
          inp = '<input class="hb-input" type="tel" name="phone" placeholder="+56 9 xxxx xxxx" />';
        }} else {{
          var cf = CF_MAP[key];
          if (!cf) return '';
          var req = cf.required ? ' *' : '';
          lbl = '<label class="hb-label">' + cf.label + req + '</label>';
          if (cf.type === 'select') {{
            var opts = '<option value="">' + (cf.placeholder||'Seleccionar…') + '</option>';
            var hasOtro = false;
            (cf.options||[]).forEach(function(o){{
              opts += '<option value="'+o+'">'+o+'</option>';
              if (o.toLowerCase() === 'otro' || o.toLowerCase() === 'otra') hasOtro = true;
            }});
            var otroInput = hasOtro
              ? '<input class="hb-input hb-otro-inp" type="text" name="' + key + '_otro" placeholder="¿Cuál?" style="display:none;margin-top:-4px" />'
              : '';
            inp = '<select class="hb-input' + (hasOtro?' hb-otro-sel':'') + '" name="' + key + '"' + (cf.required?' required':'') + '>' + opts + '</select>' + otroInput;
          }} else if (cf.type === 'textarea') {{
            inp = '<textarea class="hb-input" name="' + key + '" placeholder="' + (cf.placeholder||'') + '" rows="2"' + (cf.required?' required':'') + ' style="resize:none"></textarea>';
          }} else {{
            inp = '<input class="hb-input" type="' + cf.type + '" name="' + key + '" placeholder="' + (cf.placeholder||'') + '"' + (cf.required?' required':'') + ' />';
          }}
        }}
        return lbl + inp;
      }}

      // ── Build popup HTML ────────────────────────────────────────────────────
      function buildPopup() {{
        var useSteps = C.steps && C.steps.length > 0;
        var steps    = useSteps ? C.steps : [{{
          step: 1,
          title: C.title,
          description: C.description,
          fields: (C.collect_name ? ['name'] : []).concat(['email']).concat(C.collect_phone ? ['phone'] : []).concat((C.custom_fields||[]).map(function(f){{return f.key;}})),
          button_text: C.button_text,
        }}];

        var headerTitle = steps[0].title || C.title;
        var headerDesc  = steps[0].description || C.description;

        var progressHtml = '';
        if (steps.length > 1) {{
          progressHtml = '<div id="hb-popup-progress">';
          steps.forEach(function(_,i){{
            progressHtml += '<div class="hb-progress-dot' + (i===0?' hb-done':'') + '" id="hb-dot-'+i+'"></div>';
          }});
          progressHtml += '</div>';
        }}

        // Determine which is the last submit step (coupon step is shown after submit, not submitted)
        var lastSubmitIdx = steps.length - 1;
        for (var _si = steps.length - 1; _si >= 0; _si--) {{
          if (!steps[_si].coupon_step) {{ lastSubmitIdx = _si; break; }}
        }}

        var stepsHtml = '';
        steps.forEach(function(s,idx){{
          var isCouponStep = !!s.coupon_step;
          var fieldsHtml = '';
          if (!isCouponStep) {{
            (s.fields||[]).forEach(function(k){{ fieldsHtml += renderField(k); }});
          }}
          var isFinal = (idx === lastSubmitIdx);
          var btnText = s.button_text || (isFinal && !isCouponStep ? C.button_text : isCouponStep ? 'Ir a la tienda →' : 'Continuar →');

          if (isCouponStep) {{
            // Coupon step: shown after submit, not a real form step
            stepsHtml += '<div class="hb-step" id="hb-step-'+idx+'" style="text-align:center;padding-top:4px">' +
              '<div style="font-size:36px;margin-bottom:8px">🎉</div>' +
              '<div class="hb-coupon-box" id="hb-coupon-box">' +
              '<p style="margin:0 0 6px;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;font-weight:700">Tu cupón</p>' +
              '<p style="margin:0;font-size:26px;font-weight:900;color:'+btnBg+';letter-spacing:4px" id="hb-coupon-code">' + (C.coupon_code||'') + '</p>' +
              (s.description ? '<p style="margin:8px 0 0;font-size:13px;color:#475569">'+s.description+'</p>' : '') +
              '</div>' +
              '<button type="button" onclick="window.open(\'https://happylapiz.cl\',\'_blank\')" style="width:100%;padding:12px;background:linear-gradient(135deg,'+btnBg+','+btnBg2+');color:'+btnTxt+';border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;margin-top:4px;font-family:inherit">' + btnText + '</button>' +
              '</div>';
          }} else {{
            stepsHtml += '<div class="hb-step'+(idx===0?' hb-active':'')+'" id="hb-step-'+idx+'">' +
              fieldsHtml +
              '<button id="hb-popup-btn" type="button" data-step="'+idx+'" data-final="'+(isFinal?'1':'0')+'">' + btnText + '</button>' +
              '</div>';
          }}
        }});

        var couponPlaceholder = (C.coupon_code || C.has_dynamic_coupon)
          ? '<div class="hb-coupon-box" id="hb-coupon-box" style="display:none">' +
            '<p style="margin:0 0 6px;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;font-weight:700">Tu cupón</p>' +
            '<p style="margin:0;font-size:26px;font-weight:900;color:' + btnBg + ';letter-spacing:4px" id="hb-coupon-code">' + (C.coupon_code||'') + '</p>' +
            '<p style="margin:8px 0 0;font-size:12px;color:#64748b">Úsalo en tu próxima compra</p>' +
            '</div>'
          : '';

        return (
          '<div id="hb-popup-header">' +
          '  <button id="hb-popup-close" aria-label="Cerrar">&#x2715;</button>' +
          '  <h2 id="hb-popup-title">' + headerTitle + '</h2>' +
          (headerDesc ? '  <p id="hb-popup-subtitle">' + headerDesc + '</p>' : '') +
          '</div>' +
          '<div id="hb-popup-body">' +
          progressHtml +
          '  <form id="hb-popup-form" novalidate>' + stepsHtml + '</form>' +
          '  <div id="hb-popup-success">' +
          '    <div style="font-size:40px;margin-bottom:8px;">&#x2705;</div>' +
          '    <p style="color:#166534;font-weight:700;font-size:15px;margin:0 0 12px">' + C.success_message + '</p>' +
          couponPlaceholder +
          '  </div>' +
          '  <p id="hb-popup-fine">Respetamos tu privacidad. Puedes darte de baja cuando quieras.</p>' +
          '</div>'
        );
      }}

      // ── Show popup ──────────────────────────────────────────────────────────
      function showPopup() {{
        if (document.getElementById('hb-popup-overlay')) return;

        var overlay = document.createElement('div');
        overlay.id = 'hb-popup-overlay';
        var box = document.createElement('div');
        box.id = 'hb-popup-box';

        if (C.html_override) {{
          overlay.classList.add('hb-centered');
          box.innerHTML = C.html_override;
          overlay.addEventListener('click', function(e) {{ if (e.target === overlay) closePopup(); }});
        }} else {{
          box.innerHTML = buildPopup();
        }}

        overlay.appendChild(box);
        document.body.appendChild(overlay);

        // Wire "Otro/Otra" select fields: show text input when selected
        box.querySelectorAll('select.hb-otro-sel').forEach(function(sel) {{
          var inp = sel.parentNode ? sel.parentNode.querySelector('.hb-otro-inp') : null;
          if (!inp) return;
          function _chk() {{
            var isOtro = sel.value.toLowerCase() === 'otro' || sel.value.toLowerCase() === 'otra';
            inp.style.display = isOtro ? 'block' : 'none';
            inp.required = isOtro;
          }}
          sel.addEventListener('change', _chk);
        }});

        var closeBtn = document.getElementById('hb-popup-close');
        if (closeBtn) closeBtn.addEventListener('click', closePopup);

        var currentStep = 0;
        var collectedData = {{ source_url: window.location.href, extra_data: {{}} }};

        function collectStep(stepEl) {{
          var inputs = stepEl.querySelectorAll('input[name],select[name],textarea[name]');
          var otroValues = {{}};
          // First pass: collect _otro fields
          inputs.forEach(function(el) {{
            if (el.name && el.name.endsWith('_otro') && el.value.trim()) {{
              var baseKey = el.name.slice(0, -5);
              otroValues[baseKey] = el.value.trim();
            }}
          }});
          // Second pass: collect main fields, replacing "Otro/Otra" with the typed value
          inputs.forEach(function(el) {{
            var n = el.name, v = el.value;
            if (n.endsWith('_otro')) return; // handled above
            if ((v.toLowerCase() === 'otro' || v.toLowerCase() === 'otra') && otroValues[n]) v = otroValues[n];
            if (n === 'email')     collectedData.email = v;
            else if (n === 'name') collectedData.name  = v;
            else if (n === 'phone')collectedData.phone = v;
            else collectedData.extra_data[n] = v;
          }});
        }}

        function advanceStep(nextIdx) {{
          var steps = document.querySelectorAll('.hb-step');
          steps.forEach(function(s){{ s.classList.remove('hb-active'); }});
          var ns = document.getElementById('hb-step-' + nextIdx);
          if (ns) ns.classList.add('hb-active');
          // Update progress dots
          document.querySelectorAll('.hb-progress-dot').forEach(function(dot, i) {{
            dot.classList.toggle('hb-done', i <= nextIdx);
          }});
          // Update header
          var stepCfgs = (C.steps && C.steps.length > 0) ? C.steps : null;
          if (stepCfgs && stepCfgs[nextIdx]) {{
            var t = document.getElementById('hb-popup-title');
            var s = document.getElementById('hb-popup-subtitle');
            if (t && stepCfgs[nextIdx].title) t.textContent = stepCfgs[nextIdx].title;
            if (s && stepCfgs[nextIdx].description) s.textContent = stepCfgs[nextIdx].description;
          }}
        }}

        document.addEventListener('click', function handler(e) {{
          var btn = e.target.closest('#hb-popup-btn');
          if (!btn) return;

          var stepIdx  = parseInt(btn.dataset.step, 10);
          var isFinal  = btn.dataset.final === '1';
          var stepEl   = document.getElementById('hb-step-' + stepIdx);

          // Validate required fields in this step
          var invalid = false;
          if (stepEl) {{
            stepEl.querySelectorAll('input[required],select[required],textarea[required]').forEach(function(el) {{
              if (!el.value.trim()) {{ el.style.borderColor = '#dc2626'; invalid = true; }}
              else el.style.borderColor = '';
            }});
          }}
          if (invalid) return;

          if (stepEl) collectStep(stepEl);

          if (!isFinal) {{
            currentStep = stepIdx + 1;
            advanceStep(currentStep);
            return;
          }}

          // Final step: submit
          btn.disabled = true;
          btn.textContent = 'Enviando…';

          var payload = Object.assign({{}}, collectedData);
          if (!Object.keys(payload.extra_data||{{}}).length) delete payload.extra_data;
          if (_abVariant) payload.ab_variant = String(_abVariant.id);

          fetch(C.api + '/api/forms/' + C.id + '/submit', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(payload),
          }})
          .then(function(r) {{ return r.json(); }})
          .then(function(res) {{
            var code = res.coupon_code || C.coupon_code || '';
            // Check if there's a coupon step to advance to
            var couponStepIdx = -1;
            if (C.steps && C.steps.length > 0) {{
              for (var _ci = 0; _ci < C.steps.length; _ci++) {{
                if (C.steps[_ci].coupon_step) {{ couponStepIdx = _ci; break; }}
              }}
            }}
            if (couponStepIdx >= 0) {{
              // Advance to coupon step
              advanceStep(couponStepIdx);
              document.getElementById('hb-popup-form').style.display = 'none';
              if (document.getElementById('hb-popup-progress')) document.getElementById('hb-popup-progress').style.display = 'none';
              var couponStepEl = document.getElementById('hb-step-' + couponStepIdx);
              if (couponStepEl) couponStepEl.style.display = 'block';
              if (code) {{
                var codeEl = document.getElementById('hb-coupon-code');
                if (codeEl) codeEl.textContent = code;
              }}
              // Update header for coupon step
              var cs = C.steps[couponStepIdx];
              if (cs) {{
                var t = document.getElementById('hb-popup-title');
                var s2 = document.getElementById('hb-popup-subtitle');
                if (t && cs.title) t.textContent = cs.title;
                if (s2) s2.textContent = cs.description || '';
              }}
            }} else {{
              // No coupon step: show regular success screen
              document.getElementById('hb-popup-form').style.display = 'none';
              if (document.getElementById('hb-popup-progress')) document.getElementById('hb-popup-progress').style.display = 'none';
              var suc = document.getElementById('hb-popup-success');
              if (suc) suc.style.display = 'block';
              if (code) {{
                var box2 = document.getElementById('hb-coupon-box');
                var codeEl2 = document.getElementById('hb-coupon-code');
                if (box2) box2.style.display = 'block';
                if (codeEl2) codeEl2.textContent = code;
              }}
            }}
            _ls.setItem(STORE_KEY, 'submitted');
            setTimeout(closePopup, 10000);
          }})
          .catch(function() {{
            btn.disabled = false;
            btn.style.background = '#dc2626';
            btn.textContent = 'Error — intenta de nuevo';
          }});
        }});
      }}

      function closePopup() {{
        var el = document.getElementById('hb-popup-overlay');
        if (el) el.parentNode.removeChild(el);
        _ss.setItem(STORE_KEY + '_d', '1');
      }}

      // Triggers: activate delay AND/OR scroll (whichever fires first shows the popup)
      if (C.trigger === 'exit_intent') {{
        document.addEventListener('mouseleave', function h(e) {{
          if (e.clientY <= 0) {{ showPopup(); document.removeEventListener('mouseleave', h); }}
        }});
      }} else {{
        var _triggered = false;
        function _triggerOnce() {{ if (!_triggered) {{ _triggered = true; showPopup(); }} }}
        if (C.delay_seconds > 0) {{
          setTimeout(_triggerOnce, C.delay_seconds * 1000);
        }}
        if (C.scroll_pct > 0) {{
          window.addEventListener('scroll', function _sh() {{
            var pct = (window.scrollY / Math.max(1, document.body.scrollHeight - window.innerHeight)) * 100;
            if (pct >= C.scroll_pct) {{ _triggerOnce(); window.removeEventListener('scroll', _sh); }}
          }});
        }}
        if (C.delay_seconds <= 0 && C.scroll_pct <= 0) {{
          setTimeout(_triggerOnce, 5000);
        }}
      }}
    }})();
    """).strip()


# ── Gift recipients (regalados) ───────────────────────────────────────────────

@router.get("/gift/relaciones")
def get_relaciones():
    """Opciones de relación para el formulario de regalos (público)."""
    return {"relaciones": RELACION_OPTIONS}


@router.options("/gift/submit")
def gift_submit_preflight():
    return Response(status_code=204, headers=_cors_headers())


@router.post("/gift/submit")
def submit_gift_form(
    payload: GiftRecipientCreate,
    response: Response,
    session: Session = Depends(get_session),
):
    """Endpoint público — recibe datos del popup de regalos en happylapiz.cl."""
    for k, v in _cors_headers().items():
        response.headers[k] = v

    email = payload.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")

    contact = session.exec(select(Contact).where(Contact.email == email)).first()
    contact_id = contact.id if contact else None

    recipient = GiftRecipient(
        email=email,
        relacion=payload.relacion,
        nombre_regalado=payload.nombre_regalado.strip(),
        fecha_nacimiento_regalado=payload.fecha_nacimiento_regalado,
        contact_id=contact_id,
        source_url=payload.source_url,
    )
    session.add(recipient)
    session.commit()
    session.refresh(recipient)
    return {"ok": True, "id": recipient.id}


@router.get("/gift/recipients", response_model=List[GiftRecipientRead])
def list_gift_recipients(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
    _: User = Depends(get_current_user),
):
    return session.exec(
        select(GiftRecipient).order_by(GiftRecipient.created_at.desc()).offset(skip).limit(limit)
    ).all()


@router.get("/gift/embed.js")
def gift_embed_js():
    """Script embebible para el popup de regalos en happylapiz.cl."""
    api = settings.BACKEND_PUBLIC_URL
    relaciones = RELACION_OPTIONS
    rel_options = "".join(f'<option value="{r}">{r.capitalize()}</option>' for r in relaciones)

    js = f"""(function(){{
  var API='{api}';
  var STORE_KEY='hl_gift_popup';
  if(sessionStorage.getItem(STORE_KEY)) return;

  function injectStyles(){{
    if(document.getElementById('hl-gift-styles')) return;
    var s=document.createElement('style');
    s.id='hl-gift-styles';
    s.textContent='#hl-gift-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:99999;display:flex;align-items:center;justify-content:center;padding:16px}}'+
      '#hl-gift-box{{background:#fff;border-radius:20px;padding:32px 28px;max-width:420px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.25);font-family:Poppins,Arial,sans-serif}}'+
      '#hl-gift-box h2{{margin:0 0 6px;font-size:20px;color:#111;font-weight:700}}'+
      '#hl-gift-box p{{margin:0 0 20px;font-size:14px;color:#666}}'+
      '.hl-input{{width:100%;box-sizing:border-box;border:1.5px solid #e5e7eb;border-radius:10px;padding:11px 14px;font-size:14px;margin-bottom:12px;outline:none;font-family:inherit}}'+
      '.hl-input:focus{{border-color:#ffd51e}}'+
      '.hl-btn{{width:100%;background:#ffd51e;color:#111;border:none;border-radius:10px;padding:13px;font-size:15px;font-weight:700;cursor:pointer;margin-top:4px}}'+
      '.hl-btn:hover{{background:#ffc827}}'+
      '#hl-gift-close{{position:absolute;top:12px;right:14px;background:none;border:none;font-size:20px;cursor:pointer;color:#999}}'+
      '#hl-gift-success{{display:none;text-align:center;padding:16px 0}}'+
      'label.hl-lbl{{display:block;font-size:12px;font-weight:600;color:#555;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px}}';
    document.head.appendChild(s);
  }}

  function buildPopup(){{
    var overlay=document.createElement('div');
    overlay.id='hl-gift-overlay';
    overlay.innerHTML='<div id="hl-gift-box" style="position:relative">'+
      '<button id="hl-gift-close" aria-label="Cerrar">&times;</button>'+
      '<h2>&#127873; ¿Quién recibe el regalo?</h2>'+
      '<p>Cuéntanos un poco para enviarte recordatorios especiales antes de su cumpleaños.</p>'+
      '<div id="hl-gift-form">'+
      '<label class="hl-lbl">Tu email</label>'+
      '<input class="hl-input" id="hl-email" type="email" placeholder="tucorreo@ejemplo.com" required />'+
      '<label class="hl-lbl">¿Para quién es el regalo?</label>'+
      '<select class="hl-input" id="hl-relacion"><option value="">Selecciona...</option>'+
      '{rel_options}'+
      '</select>'+
      '<label class="hl-lbl">¿Cómo se llama?</label>'+
      '<input class="hl-input" id="hl-nombre" type="text" placeholder="Nombre del regalado" />'+
      '<label class="hl-lbl">Fecha de nacimiento</label>'+
      '<input class="hl-input" id="hl-fecha" type="date" />'+
      '<button class="hl-btn" id="hl-gift-btn">Guardar &#127881;</button>'+
      '</div>'+
      '<div id="hl-gift-success">'+
      '<div style="font-size:48px;margin-bottom:12px">&#127881;</div>'+
      '<p style="font-size:16px;font-weight:700;color:#111;margin:0 0 8px">¡Listo!</p>'+
      '<p style="color:#666;font-size:14px;margin:0">Te avisaremos antes de su cumpleaños.</p>'+
      '</div>'+
      '</div>';
    document.body.appendChild(overlay);

    document.getElementById('hl-gift-close').onclick=closePopup;
    overlay.onclick=function(e){{if(e.target===overlay)closePopup();}};

    document.getElementById('hl-gift-btn').onclick=function(){{
      var email=document.getElementById('hl-email').value.trim();
      var relacion=document.getElementById('hl-relacion').value;
      var nombre=document.getElementById('hl-nombre').value.trim();
      var fecha=document.getElementById('hl-fecha').value;
      if(!email||!relacion||!nombre){{alert('Por favor completa email, relación y nombre.');return;}}
      var btn=document.getElementById('hl-gift-btn');
      btn.disabled=true;btn.textContent='Guardando...';
      fetch(API+'/api/forms/gift/submit',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{email:email,relacion:relacion,nombre_regalado:nombre,fecha_nacimiento_regalado:fecha||null,source_url:location.href}})
      }}).then(function(r){{return r.json();}}).then(function(){{
        document.getElementById('hl-gift-form').style.display='none';
        document.getElementById('hl-gift-success').style.display='block';
        sessionStorage.setItem(STORE_KEY,'done');
        setTimeout(closePopup,4000);
      }}).catch(function(){{btn.disabled=false;btn.textContent='Error — intenta de nuevo';}});
    }};
  }}

  function closePopup(){{
    var el=document.getElementById('hl-gift-overlay');
    if(el)el.parentNode.removeChild(el);
    sessionStorage.setItem(STORE_KEY,'1');
  }}

  injectStyles();
  setTimeout(function(){{buildPopup();}},8000);
}})();
"""
    return PlainTextResponse(
        js,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Access-Control-Allow-Origin": "*"},
    )
