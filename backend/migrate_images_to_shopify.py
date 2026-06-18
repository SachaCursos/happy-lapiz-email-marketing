"""
Migrates all non-Shopify image URLs in email templates to Shopify Files CDN.

Usage:
    SHOPIFY_ACCESS_TOKEN=shpat_xxx python3 migrate_images_to_shopify.py

Or hardcode the token below before running.
"""
import os, re, sys, time
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

# ── Config ────────────────────────────────────────────────────────────────────
DB = "postgresql://postgres:nfKjyKqezPIGMgmneHgxdscnCFXypQQq@switchyard.proxy.rlwy.net:22708/railway"
SHOPIFY_DOMAIN = "happy-lapiz.myshopify.com"
SHOPIFY_TOKEN  = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")   # set via env var

GQL_URL  = f"https://{SHOPIFY_DOMAIN}/admin/api/2024-01/graphql.json"
HEADERS  = {"X-Shopify-Access-Token": SHOPIFY_TOKEN, "Content-Type": "application/json"}

# Only migrate images NOT already on Shopify CDN
SKIP_DOMAINS = ("cdn.shopify.com",)

# ── Helpers ───────────────────────────────────────────────────────────────────

def find_image_urls(html: str) -> list[str]:
    """Return all unique src= URLs from <img> tags."""
    return list(dict.fromkeys(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)))


def should_migrate(url: str) -> bool:
    return not any(url.startswith(f"https://{d}") or url.startswith(f"http://{d}") for d in SKIP_DOMAINS)


def upload_to_shopify(url: str) -> str | None:
    """Download image from url, upload to Shopify Files, return CDN url."""
    # 1. Download the image
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        print(f"    SKIP (download failed): {e}")
        return None

    content   = r.content
    mime_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    filename  = url.split("/")[-1].split("?")[0] or "image.jpg"
    file_size = len(content)

    # 2. Get staged upload target
    stage_q = """
    mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
      stagedUploadsCreate(input: $input) {
        stagedTargets { url resourceUrl parameters { name value } }
        userErrors { field message }
      }
    }"""
    stage_v = {"input": [{"filename": filename, "mimeType": mime_type,
                           "resource": "FILE", "fileSize": str(file_size), "httpMethod": "POST"}]}

    res = httpx.post(GQL_URL, headers=HEADERS, json={"query": stage_q, "variables": stage_v}, timeout=30)
    data = res.json()
    gql_data = data.get("data") or {}
    if not gql_data:
        print(f"    SKIP (Shopify GQL error): {data}")
        return None
    stage_result = gql_data.get("stagedUploadsCreate") or {}
    targets = stage_result.get("stagedTargets", [])
    errors  = stage_result.get("userErrors", [])
    if errors or not targets:
        print(f"    SKIP (stage error): {errors or data}")
        return None

    target       = targets[0]
    upload_url   = target["url"]
    resource_url = target["resourceUrl"]
    params       = {p["name"]: p["value"] for p in target["parameters"]}

    # 3. Upload to S3
    r2 = httpx.post(upload_url, data=params, files={"file": (filename, content, mime_type)}, timeout=60)
    if r2.status_code not in (200, 201, 204):
        print(f"    SKIP (S3 error {r2.status_code}): {r2.text[:100]}")
        return None

    # 4. Register in Shopify Files
    create_q = """
    mutation fileCreate($files: [FileCreateInput!]!) {
      fileCreate(files: $files) {
        files {
          ... on MediaImage { image { url } }
          ... on GenericFile { url }
        }
        userErrors { field message }
      }
    }"""
    create_v = {"files": [{"originalSource": resource_url, "contentType": "IMAGE"}]}
    r3 = httpx.post(GQL_URL, headers=HEADERS, json={"query": create_q, "variables": create_v}, timeout=30)
    data3   = r3.json()
    fc      = (data3.get("data") or {}).get("fileCreate") or {}
    files   = [f for f in fc.get("files", []) if f]
    errors3 = fc.get("userErrors", [])

    cdn_url = None
    for f in files:
        cdn_url = (f.get("image") or {}).get("url") or f.get("url")
        if cdn_url:
            break

    # Shopify processes files asynchronously — poll for the CDN URL
    if not cdn_url:
        for _ in range(4):
            time.sleep(3)
            poll_q = """
            query getFile($query: String!) {
              files(first: 1, query: $query) {
                nodes {
                  ... on MediaImage { image { url } }
                  ... on GenericFile { url }
                }
              }
            }"""
            rp = httpx.post(GQL_URL, headers=HEADERS,
                            json={"query": poll_q, "variables": {"query": f"filename:{filename}"}},
                            timeout=30)
            nodes = (rp.json().get("data") or {}).get("files", {}).get("nodes", [])
            for node in nodes:
                cdn_url = (node.get("image") or {}).get("url") or node.get("url")
                if cdn_url:
                    break
            if cdn_url:
                break

    return cdn_url or resource_url


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not SHOPIFY_TOKEN:
        print("ERROR: set SHOPIFY_ACCESS_TOKEN env var before running.")
        sys.exit(1)

    conn = psycopg2.connect(DB)
    cur  = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id, name, html_content FROM templates WHERE html_content IS NOT NULL AND html_content != ''")
    templates = cur.fetchall()
    print(f"Found {len(templates)} templates with HTML content.\n")

    url_cache: dict[str, str] = {}  # original_url -> shopify_url  (avoid re-uploading same image)
    total_replaced = 0

    for tpl in templates:
        tpl_id   = tpl["id"]
        tpl_name = tpl["name"]
        html     = tpl["html_content"]

        imgs = [u for u in find_image_urls(html) if should_migrate(u)]
        if not imgs:
            print(f"[{tpl_id}] {tpl_name} — no images to migrate")
            continue

        print(f"\n[{tpl_id}] {tpl_name} — {len(imgs)} image(s) to migrate:")
        new_html   = html
        changed    = False

        for orig_url in imgs:
            if orig_url in url_cache:
                cdn_url = url_cache[orig_url]
                print(f"  (cached) {orig_url[:70]}...")
            else:
                print(f"  Uploading: {orig_url[:70]}...")
                cdn_url = upload_to_shopify(orig_url)
                if cdn_url:
                    url_cache[orig_url] = cdn_url
                    print(f"  -> {cdn_url[:70]}...")
                else:
                    print(f"  -> FAILED, keeping original URL")
                    continue

            new_html = new_html.replace(orig_url, cdn_url)
            changed  = True
            total_replaced += 1

        if changed:
            cur.execute(
                "UPDATE templates SET html_content = %s, updated_at = NOW() WHERE id = %s",
                (new_html, tpl_id)
            )
            conn.commit()
            print(f"  Saved template {tpl_id}.")

    cur.close()
    conn.close()
    print(f"\nDone. {total_replaced} image URL(s) replaced across {len(templates)} templates.")


if __name__ == "__main__":
    main()
