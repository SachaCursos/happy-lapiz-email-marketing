/** Base URL for public-facing pages (surveys, etc.). Prefer NEXT_PUBLIC_SURVEY_BASE_URL on production. */
export function publicAppBase(): string {
  const fromEnv =
    process.env.NEXT_PUBLIC_SURVEY_BASE_URL || process.env.NEXT_PUBLIC_APP_URL;
  if (fromEnv) {
    return fromEnv.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  return "";
}

export function publicAppUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const base = publicAppBase();
  return base ? `${base}${normalized}` : normalized;
}

/** Public survey link shown in emails and the dashboard (www.happylapiz.cl/encuestas/...). */
export function surveyPublicUrl(slug: string): string {
  return publicAppUrl(`/encuestas/${slug}`);
}
