"""app/routers/forms.py — /gift/submit and /gift/embed.js were unreachable in
production: /{form_id}/submit and /{form_id}/embed.js were registered earlier
in the file, and FastAPI matches routes in registration order, so a request to
/api/forms/gift/submit matched /{form_id}/submit first with form_id="gift"
(a 422 int-parsing error) instead of ever reaching the real handler. Found
while live-testing the gift widget end-to-end. Regression guard: every
literal /gift/* route must be registered before the first /{form_id}/...
route."""
from app.routers import forms


def test_gift_routes_precede_form_id_routes():
    routes = forms.router.routes
    first_param_idx = next(
        i for i, r in enumerate(routes) if r.path.startswith("/{form_id}")
    )
    gift_indices = [i for i, r in enumerate(routes) if r.path.startswith("/gift/")]
    assert gift_indices, "no /gift/* routes found — did the route paths change?"
    assert all(i < first_param_idx for i in gift_indices), (
        "a /gift/* route is registered after a /{form_id}/... route — it will "
        "be shadowed and unreachable (form_id will try to parse the literal "
        "path segment, e.g. 'gift', as an int and fail)"
    )
