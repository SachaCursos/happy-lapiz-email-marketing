"""Form embed loader snippet + Shopify script-tag sync."""

from __future__ import annotations

import logging
import re
from datetime import datetime

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.models.form import SignupForm

logger = logging.getLogger(__name__)

_FORM_SCRIPT_RE = re.compile(r"/api/forms/(\d+)/(embed|loader)\.js")


def form_loader_url(form: SignupForm) -> str:
    api = settings.BACKEND_PUBLIC_URL.rstrip("/")
    v = form.updated_at.isoformat() if form.updated_at else datetime.utcnow().isoformat()
    return f"{api}/api/forms/{form.id}/loader.js?v={v}"


def build_loader_js(form: SignupForm) -> str:
    """
    Solo carga embed.js con versión para cache-bust.
    No modifica triggers, diseño ni envío — toda la lógica sigue en embed.js.
    """
    api = settings.BACKEND_PUBLIC_URL.rstrip("/")
    fid = form.id
    v = form.updated_at.isoformat() if form.updated_at else datetime.utcnow().isoformat()
    return f"""(function(){{
  var API={api!r}, FID={fid}, V={v!r};
  if (window.__hbFormLoader && window.__hbFormLoader[FID]) return;
  window.__hbFormLoader = window.__hbFormLoader || {{}};
  window.__hbFormLoader[FID] = true;
  var s = document.createElement('script');
  s.src = API + '/api/forms/' + FID + '/embed.js?v=' + encodeURIComponent(V);
  (document.head || document.documentElement).appendChild(s);
}})();
"""


def build_install_snippet(form: SignupForm) -> str:
    return f'<script src="{form_loader_url(form)}" async></script>'


def _shopify_headers() -> dict[str, str]:
    return {
        "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }


def sync_form_embed_to_shopify(session: Session, form_id: int | None = None) -> dict:
    """Actualiza o crea script tags en Shopify para formularios activos."""
    token = settings.SHOPIFY_ACCESS_TOKEN
    domain = settings.SHOPIFY_DOMAIN
    if not token or not domain:
        return {"ok": False, "error": "Shopify no configurado"}

    if form_id:
        form = session.get(SignupForm, form_id)
        forms = [form] if form and form.status == "active" else []
    else:
        forms = session.exec(
            select(SignupForm).where(SignupForm.status == "active")
        ).all()

    if not forms:
        return {"ok": False, "error": "Sin formularios activos"}

    headers = _shopify_headers()
    base = f"https://{domain}/admin/api/2024-10"
    list_r = httpx.get(f"{base}/script_tags.json", headers=headers, timeout=15)
    if list_r.status_code != 200:
        return {"ok": False, "error": f"No se pudieron listar script tags: {list_r.text[:200]}"}

    tags = list_r.json().get("script_tags", [])
    results = []

    for form in forms:
        loader_url = form_loader_url(form)
        loader_prefix = f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/forms/{form.id}/loader.js"

        for tag in tags:
            src = tag.get("src") or ""
            m = _FORM_SCRIPT_RE.search(src)
            if not m or int(m.group(1)) != form.id:
                continue
            if src.startswith(loader_prefix) and src == loader_url:
                continue
            tag_id = tag.get("id")
            if tag_id:
                httpx.delete(f"{base}/script_tags/{tag_id}.json", headers=headers, timeout=15)

        list_r = httpx.get(f"{base}/script_tags.json", headers=headers, timeout=15)
        tags = list_r.json().get("script_tags", []) if list_r.status_code == 200 else []

        existing = next((t for t in tags if (t.get("src") or "").startswith(loader_prefix)), None)
        if existing:
            tag_id = existing["id"]
            put_r = httpx.put(
                f"{base}/script_tags/{tag_id}.json",
                headers=headers,
                json={"script_tag": {"id": tag_id, "src": loader_url}},
                timeout=15,
            )
            ok = put_r.status_code == 200
            results.append({
                "form_id": form.id,
                "form_name": form.name,
                "action": "updated",
                "ok": ok,
                "src": loader_url,
                "tag_id": tag_id,
            })
        else:
            post_r = httpx.post(
                f"{base}/script_tags.json",
                headers=headers,
                json={"script_tag": {"event": "onload", "src": loader_url}},
                timeout=15,
            )
            ok = post_r.status_code in (200, 201)
            tag = post_r.json().get("script_tag", {}) if ok else {}
            results.append({
                "form_id": form.id,
                "form_name": form.name,
                "action": "created",
                "ok": ok,
                "src": loader_url,
                "tag_id": tag.get("id"),
                "error": None if ok else post_r.text[:200],
            })

    return {"ok": all(r.get("ok") for r in results), "forms": results}


def log_shopify_form_sync(session: Session) -> None:
    result = sync_form_embed_to_shopify(session)
    if result.get("ok"):
        logger.info("Shopify form loader sync: %s", result.get("forms"))
    else:
        logger.warning("Shopify form loader sync failed: %s", result.get("error"))
