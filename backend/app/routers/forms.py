import json
import textwrap
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.deps import get_current_user, require_editor
from app.database import get_session
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
        session.add(Contact(
            email=email,
            name=(payload.name or "").strip() or None,
            phone=(payload.phone or "").strip() or None,
            origin_utm=origin,
            opted_in=True,
            opted_in_at=datetime.utcnow(),
        ))

    session.add(FormSubmission(
        form_id=form_id,
        email=email,
        name=(payload.name or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        source_url=payload.source_url,
        extra_data=payload.extra_data or None,
    ))
    session.commit()
    return {"ok": True}


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
        "api": settings.BACKEND_PUBLIC_URL,
    }

    js = _build_embed_js(cfg)
    return PlainTextResponse(
        js,
        media_type="application/javascript",
        headers={**_cors_headers(), "Cache-Control": "no-cache"},
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

def _custom_field_html(field: dict) -> str:
    key = field.get("key", "")
    label = field.get("label", key)
    ftype = field.get("type", "text")
    placeholder = field.get("placeholder", "")
    required = field.get("required", False)
    options = field.get("options", [])
    req_attr = "required" if required else ""
    label_star = " *" if required else ""

    if ftype == "select":
        opts_html = f'<option value="">{placeholder or "Seleccionar…"}</option>'
        for opt in options:
            opts_html += f'<option value="{opt}">{opt}</option>'
        return (
            f'<label style="display:block;font-size:12px;color:#64748b;margin-bottom:4px">{label}{label_star}</label>'
            f'<select class="hb-input" name="{key}" {req_attr}>{opts_html}</select>'
        )
    if ftype == "textarea":
        return (
            f'<label style="display:block;font-size:12px;color:#64748b;margin-bottom:4px">{label}{label_star}</label>'
            f'<textarea class="hb-input" name="{key}" placeholder="{placeholder}" rows="2" {req_attr} style="resize:none"></textarea>'
        )
    return (
        f'<label style="display:block;font-size:12px;color:#64748b;margin-bottom:4px">{label}{label_star}</label>'
        f'<input class="hb-input" type="{ftype}" name="{key}" placeholder="{placeholder}" {req_attr} />'
    )


def _build_embed_js(cfg: dict) -> str:
    cfg_json = json.dumps(cfg, ensure_ascii=False)

    # Build custom field HTML for auto-generated mode
    custom_fields_html = ""
    for field in cfg.get("custom_fields", []):
        custom_fields_html += _custom_field_html(field)

    custom_fields_html_js = json.dumps(custom_fields_html)

    return textwrap.dedent(f"""
    (function() {{
      var C = {cfg_json};
      var STORE_KEY = 'hb_form_' + C.id;
      if (sessionStorage.getItem(STORE_KEY)) return;

      var STYLES = `
        @keyframes hbSlideUp {{
          from {{ transform:translateY(80px);opacity:0 }}
          to   {{ transform:translateY(0);opacity:1 }}
        }}
        @keyframes hbFadeIn {{
          from {{ opacity:0;transform:scale(0.96) }}
          to   {{ opacity:1;transform:scale(1) }}
        }}
        #hb-popup-overlay {{
          position:fixed;bottom:0;left:0;right:0;
          display:flex;justify-content:center;padding:16px;
          z-index:2147483647;pointer-events:none;
          font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        }}
        #hb-popup-overlay.hb-centered {{
          bottom:0;top:0;align-items:center;background:rgba(0,0,0,0.45);pointer-events:all;
        }}
        #hb-popup-box {{
          background:#fff;border-radius:16px;overflow:hidden;
          box-shadow:0 20px 60px rgba(0,0,0,0.2);
          max-width:440px;width:100%;max-height:90vh;overflow-y:auto;
          pointer-events:all;border:1px solid #e2e8f0;
        }}
        #hb-popup-overlay:not(.hb-centered) #hb-popup-box {{
          animation:hbSlideUp 0.4s cubic-bezier(0.34,1.56,0.64,1);
        }}
        #hb-popup-overlay.hb-centered #hb-popup-box {{
          animation:hbFadeIn 0.25s ease;
        }}
        #hb-popup-header {{
          background:linear-gradient(135deg,#0369a1 0%,#0ea5e9 100%);
          padding:20px 48px 20px 24px;position:relative;
        }}
        #hb-popup-close {{
          position:absolute;top:12px;right:12px;
          background:rgba(255,255,255,0.2);border:none;color:#fff;
          width:28px;height:28px;border-radius:50%;
          cursor:pointer;font-size:18px;line-height:28px;text-align:center;
          transition:background .2s;
        }}
        #hb-popup-close:hover {{ background:rgba(255,255,255,0.35); }}
        #hb-popup-brand {{ margin:0 0 4px;color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:700; }}
        #hb-popup-title {{ margin:0;color:#fff;font-size:19px;font-weight:700;line-height:1.3; }}
        #hb-popup-body {{ padding:20px 24px; }}
        #hb-popup-desc {{ margin:0 0 16px;color:#64748b;font-size:14px;line-height:1.5; }}
        .hb-input {{
          width:100%;padding:10px 14px;border:1.5px solid #e2e8f0;
          border-radius:8px;font-size:14px;color:#1e293b;
          margin-bottom:10px;box-sizing:border-box;outline:none;
          transition:border-color .2s;font-family:inherit;
        }}
        .hb-input:focus {{ border-color:#0ea5e9; }}
        #hb-popup-btn {{
          width:100%;padding:12px;
          background:linear-gradient(135deg,#0369a1,#0ea5e9);
          color:#fff;border:none;border-radius:10px;font-size:15px;
          font-weight:700;cursor:pointer;transition:opacity .2s;margin-top:4px;font-family:inherit;
        }}
        #hb-popup-btn:hover {{ opacity:0.88; }}
        #hb-popup-btn:disabled {{ opacity:0.5;cursor:not-allowed; }}
        #hb-popup-success {{ display:none;text-align:center;padding:8px 0 4px; }}
        #hb-popup-fine {{ margin:12px 0 0;color:#94a3b8;font-size:11px;text-align:center; }}
      `;
      var style = document.createElement('style');
      style.textContent = STYLES;
      document.head.appendChild(style);

      var customFieldsHtml = {custom_fields_html_js};

      function buildAutoPopup() {{
        var nameF  = C.collect_name  ? '<input class="hb-input" id="hb-inp-name"  type="text" name="name"  placeholder="Tu nombre" />' : '';
        var phoneF = C.collect_phone ? '<input class="hb-input" id="hb-inp-phone" type="tel"  name="phone" placeholder="Tu teléfono" />' : '';
        var descH  = C.description   ? '<p id="hb-popup-desc">' + C.description + '</p>' : '';
        return (
          '<div id="hb-popup-header">' +
          '  <button id="hb-popup-close" aria-label="Cerrar">&#x2715;</button>' +
          '  <p id="hb-popup-brand">HotBoat</p>' +
          '  <h2 id="hb-popup-title">' + C.title + '</h2>' +
          '</div>' +
          '<div id="hb-popup-body">' +
          '  ' + descH +
          '  <form id="hb-popup-form" novalidate>' +
          '    ' + nameF +
          '    <input class="hb-input" type="email" name="email" placeholder="Tu email *" required />' +
          '    ' + phoneF +
          '    ' + customFieldsHtml +
          '    <button id="hb-popup-btn" type="submit">' + C.button_text + '</button>' +
          '  </form>' +
          '  <div id="hb-popup-success">' +
          '    <div style="font-size:40px;margin-bottom:8px;">&#x2705;</div>' +
          '    <p style="color:#166534;font-weight:700;font-size:15px;margin:0 0 12px">' + C.success_message + '</p>' +
          (C.coupon_code ? (
          '    <div style="margin:4px 0 12px;padding:14px 20px;background:#f0f9ff;border:2px dashed #0ea5e9;border-radius:12px;text-align:center">' +
          '      <p style="margin:0 0 6px;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;font-weight:700">Tu cupón de reserva</p>' +
          '      <p style="margin:0;font-size:26px;font-weight:900;color:#0369a1;letter-spacing:4px">' + C.coupon_code + '</p>' +
          '      <p style="margin:8px 0 0;font-size:12px;color:#64748b">Úsalo al reservar en hotboat.cl</p>' +
          '    </div>'
          ) : '') +
          '  </div>' +
          '  <p id="hb-popup-fine">Respetamos tu privacidad. Puedes darte de baja cuando quieras.</p>' +
          '</div>'
        );
      }}

      function showPopup() {{
        if (document.getElementById('hb-popup-overlay')) return;

        var overlay = document.createElement('div');
        overlay.id = 'hb-popup-overlay';

        var box = document.createElement('div');
        box.id = 'hb-popup-box';

        if (C.html_override) {{
          overlay.classList.add('hb-centered');
          box.innerHTML = C.html_override;
          overlay.addEventListener('click', function(e) {{
            if (e.target === overlay) closePopup();
          }});
        }} else {{
          box.innerHTML = buildAutoPopup();
        }}

        overlay.appendChild(box);
        document.body.appendChild(overlay);

        var closeBtn = document.getElementById('hb-popup-close');
        if (closeBtn) closeBtn.addEventListener('click', closePopup);

        var form = document.getElementById('hb-popup-form');
        if (!form) return;

        form.addEventListener('submit', function(e) {{
          e.preventDefault();
          var btn = document.getElementById('hb-popup-btn');
          if (btn) {{ btn.disabled = true; btn.textContent = 'Enviando…'; }}

          // Collect ALL named inputs generically
          var data = {{ source_url: window.location.href, extra_data: {{}} }};
          var els = form.querySelectorAll('input[name],select[name],textarea[name]');
          els.forEach(function(el) {{
            var n = el.name, v = el.value;
            if (n === 'email')      data.email = v;
            else if (n === 'name')  data.name  = v;
            else if (n === 'phone') data.phone = v;
            else                    data.extra_data[n] = v;
          }});

          if (!data.email) {{
            if (btn) {{ btn.disabled = false; btn.textContent = C.button_text; }}
            return;
          }}
          if (!Object.keys(data.extra_data).length) delete data.extra_data;

          fetch(C.api + '/api/forms/' + C.id + '/submit', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data),
          }})
          .then(function(r) {{ return r.json(); }})
          .then(function() {{
            var f2 = document.getElementById('hb-popup-form');
            var s2 = document.getElementById('hb-popup-success');
            if (f2) f2.style.display = 'none';
            if (s2) s2.style.display = 'block';
            sessionStorage.setItem(STORE_KEY, 'submitted');
            setTimeout(closePopup, 6000);
          }})
          .catch(function() {{
            if (btn) {{
              btn.disabled = false;
              btn.style.background = '#dc2626';
              btn.textContent = 'Error — intenta de nuevo';
            }}
          }});
        }});
      }}

      function closePopup() {{
        var el = document.getElementById('hb-popup-overlay');
        if (el) el.parentNode.removeChild(el);
        sessionStorage.setItem(STORE_KEY, '1');
      }}

      if (C.trigger === 'delay') {{
        setTimeout(showPopup, C.delay_seconds * 1000);
      }} else if (C.trigger === 'exit_intent') {{
        document.addEventListener('mouseleave', function h(e) {{
          if (e.clientY <= 0) {{ showPopup(); document.removeEventListener('mouseleave', h); }}
        }});
      }} else if (C.trigger === 'scroll') {{
        window.addEventListener('scroll', function h() {{
          var pct = (window.scrollY / Math.max(1, document.body.scrollHeight - window.innerHeight)) * 100;
          if (pct >= C.scroll_pct) {{ showPopup(); window.removeEventListener('scroll', h); }}
        }});
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
