import axios from "axios";

// In production, NEXT_PUBLIC_BACKEND_URL is baked in at build time so the browser
// calls the backend directly (bypasses the Next.js proxy and Railway's CDN).
// In dev, falls back to the local proxy (/api → localhost:8001).
const BASE = process.env.NEXT_PUBLIC_BACKEND_URL
  ? `${process.env.NEXT_PUBLIC_BACKEND_URL}/api`
  : "/api";

export const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("hb_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    // Only force-logout if the token itself is rejected, not on any random 401.
    // Avoids logout loops caused by cold-start errors or momentary backend failures.
    if (err.response?.status === 401 && typeof window !== "undefined") {
      const url: string = err.config?.url ?? "";
      const isAuthCheck = url.includes("/auth/");
      if (isAuthCheck) {
        localStorage.removeItem("hb_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

// Auth
export const authApi = {
  login: (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    return api.post<{ access_token: string }>("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
  },
  me: () => api.get("/auth/me"),
};

// Contacts
export const contactsApi = {
  list: (params?: { skip?: number; limit?: number; search?: string; opted_in?: boolean; sort_by?: string; sort_dir?: string }) =>
    api.get("/contacts", { params }),
  stats: () => api.get("/contacts/stats"),
  get: (id: number) => api.get(`/contacts/${id}`),
  create: (data: unknown) => api.post("/contacts", data),
  update: (id: number, data: unknown) => api.patch(`/contacts/${id}`, data),
  delete: (id: number) => api.delete(`/contacts/${id}`),
  segments: (id: number) => api.get(`/contacts/${id}/segments`),
  bookings: (id: number) => api.get(`/contacts/${id}/bookings`),
  emailActivity: (id: number) => api.get(`/contacts/${id}/email_activity`),
  emailSends: (id: number) => api.get(`/contacts/${id}/email_sends`),
  importCsv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/contacts/import/csv", form);
  },
};

// Segments
export const segmentsApi = {
  list: () => api.get("/segments"),
  get: (id: number) => api.get(`/segments/${id}`),
  create: (data: unknown) => api.post("/segments", data),
  update: (id: number, data: unknown) => api.patch(`/segments/${id}`, data),
  delete: (id: number) => api.delete(`/segments/${id}`),
  preview: (id: number) => api.get(`/segments/${id}/preview`),
};

// Templates
export const templatesApi = {
  list: () => api.get("/templates"),
  get: (id: number) => api.get(`/templates/${id}`),
  create: (data: unknown) => api.post("/templates", data),
  update: (id: number, data: unknown) => api.patch(`/templates/${id}`, data),
  delete: (id: number) => api.delete(`/templates/${id}`),
  duplicate: (id: number) => api.post(`/templates/${id}/duplicate`),
};

// Campaigns
export const campaignsApi = {
  list: () => api.get("/campaigns"),
  get: (id: number) => api.get(`/campaigns/${id}`),
  create: (data: unknown) => api.post("/campaigns", data),
  update: (id: number, data: unknown) => api.patch(`/campaigns/${id}`, data),
  delete: (id: number) => api.delete(`/campaigns/${id}`),
  send: (id: number, limit?: number) => api.post(`/campaigns/${id}/send`, limit ? { limit } : {}),
  sendTest: (id: number) => api.post(`/campaigns/${id}/send-test`),
  sendProgress: (id: number) => api.get(`/campaigns/${id}/send-progress`),
  stats: (id: number) => api.get(`/campaigns/${id}/stats`),
  conversions: (id: number, days = 60) => api.get(`/campaigns/${id}/conversions?days=${days}`),
  sends: (id: number) => api.get(`/campaigns/${id}/sends`),
};

// Analytics
export const analyticsApi = {
  overview: () => api.get("/analytics/overview"),
  recentCampaigns: () => api.get("/analytics/campaigns/recent"),
  revenue: (dateFrom?: string, dateTo?: string) => {
    const params = new URLSearchParams();
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return api.get(`/analytics/revenue?${params.toString()}`);
  },
};

// Signup Forms
export const formsApi = {
  list: () => api.get("/forms"),
  get: (id: number) => api.get(`/forms/${id}`),
  create: (data: unknown) => api.post("/forms", data),
  update: (id: number, data: unknown) => api.patch(`/forms/${id}`, data),
  delete: (id: number) => api.delete(`/forms/${id}`),
  submissions: (id: number) => api.get(`/forms/${id}/submissions`),
};

// Automations
export const automationsApi = {
  list: () => api.get("/automations"),
  get: (id: number) => api.get(`/automations/${id}`),
  create: (data: unknown) => api.post("/automations", data),
  update: (id: number, data: unknown) => api.patch(`/automations/${id}`, data),
  delete: (id: number) => api.delete(`/automations/${id}`),
  toggle: (id: number) => api.post(`/automations/${id}/toggle`),
  runs: (id: number) => api.get(`/automations/${id}/runs`),
  stats: (id: number) => api.get(`/automations/${id}/stats`),
  stepStats: (id: number) => api.get(`/automations/${id}/step-stats`),
  pending: (id: number) => api.get(`/automations/${id}/pending`),
};

// Sync
export const syncApi = {
  run: () => api.post("/sync/run"),
  status: () => api.get("/sync/status"),
  importTc: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/sync/tc-import", form);
  },
};

// Admin
export const adminApi = {
  syncProducts: () => api.post("/admin/sync-products"),
  seedTemplates: () => api.post("/admin/seed-templates"),
};

// Shopify
export const shopifyApi = {
  products: () => api.get<ShopifyProduct[]>("/shopify/products"),
  collections: () => api.get<ShopifyCollection[]>("/shopify/collections"),
};

export interface ShopifyCollection {
  id: string;
  title: string;
}

export interface ShopifyProduct {
  id: string;
  title: string;
  handle: string;
  url: string;
  image_url: string;
  price: string;
  compare_at_price: string;
}
