import { NextRequest, NextResponse } from "next/server";

/** Slug segments (not numeric ids, not "new") → public survey at /encuesta/[slug]. */
function isPublicSurveySlug(segment: string): boolean {
  return segment !== "new" && !/^\d+$/.test(segment);
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const encuestasMatch = pathname.match(/^\/encuestas\/([^/]+)\/?$/);
  if (encuestasMatch && isPublicSurveySlug(encuestasMatch[1])) {
    const slug = encuestasMatch[1];
    return NextResponse.rewrite(new URL(`/encuesta/${slug}`, request.url));
  }

  const encuestaMatch = pathname.match(/^\/encuesta\/([^/]+)\/?$/);
  if (encuestaMatch) {
    const slug = encuestaMatch[1];
    return NextResponse.redirect(new URL(`/encuestas/${slug}`, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/encuestas/:path*", "/encuesta/:path*"],
};
