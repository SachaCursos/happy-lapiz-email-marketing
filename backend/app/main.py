from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.database import create_db_and_tables
from app.routers import auth, contacts, segments, templates, campaigns, webhooks, ses_webhooks, analytics, sync, automations, forms, admin, coupons, shopify_webhooks, evergreen, html_blocks, favorite_blocks, surveys, dynamic_criteria, shopify_oauth, email_log
from app.models import gift_recipient as _gift_recipient_model  # noqa: F401 — ensures table is created
from app.models import form as _form_model  # noqa: F401 — form_views table
from app.models import evergreen as _evergreen_model  # noqa: F401
from app.models import dynamic_criteria as _dynamic_criteria_model  # noqa: F401

app = FastAPI(title="Happy Lápiz Email Marketing API", version="1.0.0", redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    # "*" needed so embed.js can submit forms from any website (e.g. happylapiz.cl).
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
app.include_router(evergreen.router, prefix="/api/evergreen", tags=["evergreen"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(ses_webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(automations.router, prefix="/api/automations", tags=["automations"])
app.include_router(forms.router, prefix="/api/forms", tags=["forms"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(coupons.router, prefix="/api/coupons", tags=["coupons"])
app.include_router(shopify_webhooks.router, prefix="/api/shopify", tags=["shopify"])
app.include_router(html_blocks.router, prefix="/api/html-blocks", tags=["html-blocks"])
app.include_router(favorite_blocks.router, prefix="/api/favorite-blocks", tags=["favorite-blocks"])
app.include_router(surveys.router, prefix="/api/surveys", tags=["surveys"])
app.include_router(dynamic_criteria.router, prefix="/api/dynamic-criteria", tags=["dynamic-criteria"])
app.include_router(shopify_oauth.router, prefix="/api/shopify", tags=["shopify-oauth"])
app.include_router(email_log.router, prefix="/api/email-log", tags=["email-log"])


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    from app.services.scheduler import start_scheduler
    from app.database import engine
    from sqlmodel import Session, select
    from app.services.template_compositions import ensure_managed_block_templates
    from app.models.shop import Shop

    start_scheduler()
    try:
        with Session(engine) as session:
            # Managed block templates + REGALO birthday automation are Happy
            # Lápiz-specific seed data today — resolve its shop explicitly
            # rather than guessing "first shop in DB" once more tenants exist.
            hl_shop = session.exec(
                select(Shop).where(Shop.shopify_domain == "happy-lapiz.myshopify.com")
            ).first()
            if hl_shop:
                ensure_managed_block_templates(session, hl_shop.id)
            from app.services.birthday_automation_seed import ensure_birthday_reminder_setup
            ensure_birthday_reminder_setup(session, hl_shop)
            from app.services.email_sender import finalize_stuck_sending_campaigns
            finalize_stuck_sending_campaigns(session)
            from app.services.bounce_segment_seed import ensure_repeat_bounce_segment
            ensure_repeat_bounce_segment(session)
            from app.services.no_open_segment_seed import ensure_no_open_segment
            ensure_no_open_segment(session)
            from app.services.family_role_segment_seed import ensure_family_role_segments
            ensure_family_role_segments(session)
            from app.services.dynamic_cross_sell_seed import ensure_dynamic_cross_sell_setup
            ensure_dynamic_cross_sell_setup(session, hl_shop)
            from app.services.form_embed_snippet import log_shopify_form_sync
            log_shopify_form_sync(session)
            from app.services.form_stats import ensure_form_stats_epoch
            ensure_form_stats_epoch(session)
            from app.services.birthday_enrollment import backfill_birthday_enrollments
            backfill_birthday_enrollments(session)
    except Exception:
        pass  # DB may not be ready on first deploy tick


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/track.js")
def tracking_pixel_root():
    """Script de tracking público — sirve sin auth para Shopify Script Tags."""
    from fastapi.responses import PlainTextResponse
    backend = settings.BACKEND_PUBLIC_URL
    js = f"""(function(){{
  var API='{backend}/api/shopify/track';
  var SHOP_DOMAIN=(window.Shopify&&window.Shopify.shop)||'';
  function send(evt,data){{
    fetch(API,{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify(Object.assign({{event:evt,url:location.href,shop_domain:SHOP_DOMAIN}},data||{{}})),keepalive:true}}).catch(function(){{}});
  }}
  // Viewed Product
  if(window.meta&&window.meta.product){{
    send('viewed_product',{{product_id:String(window.meta.product.id||''),product_title:window.meta.product.title||''}});
  }}
  // Shopify Analytics product
  if(window.ShopifyAnalytics&&ShopifyAnalytics.meta&&ShopifyAnalytics.meta.product){{
    var p=ShopifyAnalytics.meta.product;
    send('viewed_product',{{product_id:String(p.id||''),product_title:p.title||''}});
  }}
  // Active on site
  try{{
    var email=(window.ShopifyAnalytics&&ShopifyAnalytics.meta&&ShopifyAnalytics.meta.email)||'';
    if(email) send('active_on_site',{{email:email}});
  }}catch(e){{}}
  // Added to cart — intercept /cart/add fetch
  var _fetch=window.fetch;
  window.fetch=function(input,init){{
    var url=typeof input==='string'?input:(input&&input.url)||'';
    if(url.indexOf('/cart/add')!==-1){{
      var body={{}};
      try{{body=JSON.parse((init&&init.body)||'{{}}');}}catch(e){{}}
      setTimeout(function(){{send('added_to_cart',{{product_id:String(body.id||''),url:location.href}});}},300);
    }}
    return _fetch.apply(this,arguments);
  }};
  // Added to cart — intercept XMLHttpRequest
  var _open=XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open=function(m,u){{
    if(u&&u.indexOf('/cart/add')!==-1){{
      setTimeout(function(){{send('added_to_cart',{{url:location.href}});}},500);
    }}
    return _open.apply(this,arguments);
  }};
}})();
"""
    return PlainTextResponse(js, media_type="application/javascript",
                             headers={"Cache-Control": "no-cache", "Access-Control-Allow-Origin": "*"})
