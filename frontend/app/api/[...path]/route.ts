import { NextRequest, NextResponse } from "next/server";

// Runtime proxy — reads BACKEND_URL at request time (no rebuild needed).
// Set BACKEND_URL in Railway frontend service Variables.
const BACKEND = (process.env.BACKEND_URL || "http://localhost:8000").replace(/\/$/, "");

async function proxy(req: NextRequest): Promise<NextResponse> {
  const path = req.nextUrl.pathname;
  const search = req.nextUrl.search;
  const target = `${BACKEND}${path}${search}`;

  const forward = new Headers();
  for (const [k, v] of req.headers.entries()) {
    const lower = k.toLowerCase();
    if (!["host", "connection", "transfer-encoding", "content-length"].includes(lower)) {
      forward.set(k, v);
    }
  }

  const hasBody = !["GET", "HEAD"].includes(req.method);
  // Read body once up-front so it can be reused on redirect
  const bodyBuffer = hasBody ? await req.arrayBuffer() : undefined;

  async function doFetch(url: string) {
    return fetch(url, {
      method: req.method,
      headers: forward,
      body: bodyBuffer,
      redirect: "manual",
    });
  }

  try {
    let upstream = await doFetch(target);

    // Follow 307/308 redirects manually so auth headers are never dropped
    if (upstream.status >= 300 && upstream.status < 400) {
      const location = upstream.headers.get("location");
      if (location) {
        const redirectTarget = location.startsWith("http") ? location : `${BACKEND}${location}`;
        upstream = await doFetch(redirectTarget);
      }
    }

    const resHeaders = new Headers();
    for (const [k, v] of upstream.headers.entries()) {
      if (!["transfer-encoding", "connection"].includes(k.toLowerCase())) {
        resHeaders.set(k, v);
      }
    }

    // Buffer the response body — streaming through Railway's CDN can drop bytes
    const resBody = await upstream.arrayBuffer();
    resHeaders.set("x-proxy-version", "v3");
    return new NextResponse(resBody, { status: upstream.status, headers: resHeaders });
  } catch {
    return NextResponse.json({ detail: "Backend no disponible" }, { status: 503 });
  }
}

export const GET    = proxy;
export const POST   = proxy;
export const PATCH  = proxy;
export const DELETE = proxy;
export const PUT    = proxy;
