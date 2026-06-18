"""
Remove HotBoat branding from all email templates.

Targets two patterns:
  1. HTML blocks containing HotBoat company name / tagline.
  2. Plain-text footers with the same content.

After removal, _inject_footer() will automatically add the
correct Happy Lápiz footer the next time each template is sent.

Run once:
    DATABASE_URL=<url> python fix_hotboat_footer.py
"""
import os
import re
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL env var is required")

# ---------------------------------------------------------------------------
# Patterns to strip
# ---------------------------------------------------------------------------

# 1. Full HTML footer block — everything from a wrapping <div> or <table> that
#    contains "HotBoat" down to its closing tag (greedy-safe, dotall).
HTML_HOTBOAT_BLOCK = re.compile(
    r'<(?:div|table)[^>]*>(?:(?!<(?:div|table))[^<]|<(?!(?:div|table)))*?'
    r'HotBoat'
    r'(?:(?!<\/(?:div|table)>).)*?<\/(?:div|table)>\s*',
    re.DOTALL | re.IGNORECASE,
)

# 2. Simpler per-element patterns for isolated <p> or <td> tags with HotBoat text.
HTML_HOTBOAT_P = re.compile(
    r'<(?:p|td)[^>]*>\s*HotBoat\s*<\/(?:p|td)>\s*',
    re.DOTALL | re.IGNORECASE,
)
HTML_EXPERIENCIAS_P = re.compile(
    r'<(?:p|td)[^>]*>\s*Experiencias en el agua[^<]*<\/(?:p|td)>\s*',
    re.DOTALL | re.IGNORECASE,
)

# 3. Plain-text footer — from the first line that is exactly "HotBoat"
#    (possibly preceded by blank lines) to the end of the string.
PLAIN_TEXT_FOOTER = re.compile(
    r'\n{1,3}HotBoat\s*\nExperiencias en el agua[^\n]*\n.*$',
    re.DOTALL | re.IGNORECASE,
)

# 4. Any remaining stray "hotboat" references in footers
HOTBOAT_STRAY = re.compile(
    r'HotBoat(?!\w)',
    re.IGNORECASE,
)


def strip_hotboat(html: str) -> str:
    original = html

    # Try complex block removal first
    html = HTML_HOTBOAT_BLOCK.sub("", html)

    # Then isolated <p>/<td> elements
    html = HTML_HOTBOAT_P.sub("", html)
    html = HTML_EXPERIENCIAS_P.sub("", html)

    # Plain-text footer (for plain-text templates)
    html = PLAIN_TEXT_FOOTER.sub("", html)

    return html.rstrip()


engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT id, name, html_content FROM templates")
    ).fetchall()

    updated = 0
    for row in rows:
        content = row.html_content or ""
        lower = content.lower()

        # Only touch templates that have HotBoat references
        if "hotboat" not in lower and "experiencias en el agua" not in lower:
            continue

        new_content = strip_hotboat(content)

        if new_content == content:
            print(f"  [skip]    id={row.id} '{row.name}' — HotBoat found but pattern not matched (manual review needed)")
            continue

        conn.execute(
            text("UPDATE templates SET html_content = :html WHERE id = :id"),
            {"html": new_content, "id": row.id},
        )
        print(f"  [updated] id={row.id} '{row.name}'")
        updated += 1

    conn.commit()

print(f"\nDone — {updated} template(s) updated.")
