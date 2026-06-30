export interface User {
  id: number;
  email: string;
  name: string;
  role: "admin" | "editor" | "viewer";
  created_at: string;
}

export interface Contact {
  id: number;
  email: string;
  name: string | null;
  phone: string | null;
  origin_utm: string | null;
  location: string | null;
  opted_in: boolean;
  opted_in_at: string | null;
  opted_out_at: string | null;
  ultima_visita: string | null;
  ticket_medio: number | null;
  custom_fields: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  // Shopify ecommerce data
  orders_count: number;
  total_spent: number | null;
  last_purchase: string | null;
  products_purchased: { title: string; cantidad_total: number }[] | null;
  shipping_city: string | null;
  shipping_province: string | null;
  all_shipping_cities: string[] | null;
  // Klaviyo data
  klaviyo_id: string | null;
  last_event_date: string | null;
  klaviyo_properties: Record<string, unknown> | null;
  klaviyo_location: { city?: string; region?: string; country?: string } | null;
  ultima_visita_web: string | null;
  accepts_marketing: boolean | null;
  smile_points: number | null;
  expected_next_order: string | null;
}

export interface ContactBooking {
  fecha: string;
  status: string;
  ingreso_total: number | null;
  como_supieron: string | null;
  extras: Record<string, unknown>;
}

export interface ContactEmailEvent {
  type: "sent" | "delivered" | "opened" | "clicked" | "bounced";
  campaign_id: number;
  campaign_name: string;
  timestamp: string;
}

export interface CampaignEmailSend {
  campaign_id: number;
  campaign_name: string;
  status: string;
  sent_at: string | null;
  delivered_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
  bounced_at: string | null;
}

export interface SegmentRule {
  field: string;
  op: string;
  value: unknown;
}

export interface SegmentConditions {
  operator: "AND" | "OR";
  rules: (SegmentRule | SegmentConditions)[];
}

export interface Segment {
  id: number;
  name: string;
  description: string | null;
  conditions: SegmentConditions | null;
  contact_count: number | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface Template {
  id: number;
  name: string;
  subject_default: string;
  preview_text: string | null;
  html_content: string;
  json_blocks: unknown[] | Record<string, unknown> | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export type CampaignStatus = "draft" | "scheduled" | "sending" | "paused" | "sent" | "cancelled";

export interface Campaign {
  id: number;
  name: string;
  subject: string;
  preview_text: string | null;
  template_id: number;
  segment_id: number;
  exclude_segment_ids: number[] | null;
  status: CampaignStatus;
  scheduled_at: string | null;
  sent_at: string | null;
  created_by: number | null;
  created_at: string;
}

export interface CampaignStats {
  campaign_id: number;
  total: number;
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  bounced: number;
  complained: number;
  open_rate: number;
  click_rate: number;
  bounce_rate: number;
}

export interface CampaignConversions {
  campaign_id: number;
  window_days: number;
  bookings: number;
  revenue: number;
  converted_contacts: number;
}

export interface CampaignAudiencePreview {
  segment_count: number;
  excluded_count: number;
  recipient_count: number;
}

export type EvergreenStatus = "active" | "paused";

export interface EvergreenStep {
  step: number;
  delay_hours: number;
  subject: string;
  template_id: number;
  preview_text?: string | null;
}

export interface EvergreenCampaign {
  id: number;
  name: string;
  subject: string;
  preview_text: string | null;
  template_id: number;
  steps: EvergreenStep[] | null;
  segment_id: number | null;
  exclude_segment_ids: number[] | null;
  sort_order: number;
  status: EvergreenStatus;
  allow_resend: boolean;
  resend_after_days: number | null;
  min_days_inactive: number;
  require_open_in_last_n: number;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface EvergreenStats {
  evergreen_id: number;
  total: number;
  sent: number;
  opened: number;
  clicked: number;
  open_rate: number;
  click_rate: number;
}

export type FormTrigger = "delay" | "exit_intent" | "scroll";

export interface FormField {
  key: string;
  label: string;
  type: "text" | "email" | "tel" | "date" | "number" | "textarea" | "select";
  required: boolean;
  placeholder?: string;
  options?: string[];
}

export interface FormDesign {
  header_bg: string;
  header_bg2: string;
  header_text: string;
  body_bg: string;
  btn_bg: string;
  btn_bg2: string;
  btn_text: string;
  input_border: string;
  border_radius: number;
  font: string;
  /** Textos personalizables del popup */
  coupon_label?: string;
  copy_button_text?: string;
  coupon_hint?: string;
  privacy_text?: string;
  add_regalado_button_text?: string;
  add_regalado_added_text?: string;
}

export interface FormStep {
  step: number;
  title: string;
  description: string;
  fields: string[];
  button_text: string;
  coupon_step?: boolean;   // last step shown after submit, displays the generated coupon
  allow_multiple_regalados?: boolean;
  /** Texto del botón para agregar otro regalado (sobreescribe el del diseño) */
  add_regalado_button_text?: string;
}

export interface AbFormVariant {
  id: string;          // "A", "B", "C"
  title: string;
  description: string;
  button_text: string;
  weight: number;
}

export interface AbFormVariantStat {
  variant_id: string;
  submissions: number;
}

export interface AbFormStats {
  total: number;
  variants: AbFormVariantStat[];
}

export interface SignupForm {
  id: number;
  name: string;
  title: string;
  description: string | null;
  button_text: string;
  success_message: string;
  collect_name: boolean;
  collect_phone: boolean;
  popup_trigger: FormTrigger;
  popup_delay_seconds: number;
  popup_scroll_pct: number;
  custom_form_fields: FormField[] | null;
  html_override: string | null;
  coupon_code: string | null;
  design_config: FormDesign | null;
  steps_config: FormStep[] | null;
  coupon_campaign_id: number | null;
  coupon_automation_id: number | null;
  ab_variants: AbFormVariant[] | null;
  status: "active" | "paused";
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface FormSubmission {
  id: number;
  form_id: number;
  email: string;
  name: string | null;
  phone: string | null;
  source_url: string | null;
  extra_data: Record<string, unknown> | null;
  coupon_code: string | null;
  ab_variant?: string | null;
  relacion_regalado?: string | null;
  nombre_regalado?: string | null;
  fecha_nacimiento_regalado?: string | null;
  relacion_regalado2?: string | null;
  nombre_regalado2?: string | null;
  fecha_nacimiento_regalado2?: string | null;
  created_at: string;
}

export interface RegaladoEntry {
  relacion: string;
  nombre: string;
  fecha: string;
}

/** Extract all gift recipients from a form submission (columns + extra_data). */
export function getRegaladosFromSubmission(s: FormSubmission): RegaladoEntry[] {
  const ed = s.extra_data;
  if (ed?.regalados && Array.isArray(ed.regalados)) {
    return (ed.regalados as Record<string, string>[])
      .map((r) => ({
        relacion: r.para_quien || r.relacion || "",
        nombre: r.destinatario_nombre || r.nombre || r.nombre_regalado || "",
        fecha: r.cual_es_su_fecha_de_nacimiento || r.destinatario_cumpleanos || r.fecha || "",
      }))
      .filter((r) => r.nombre || r.relacion);
  }

  const out: RegaladoEntry[] = [];
  if (s.nombre_regalado || s.relacion_regalado) {
    out.push({
      relacion: s.relacion_regalado || "",
      nombre: s.nombre_regalado || "",
      fecha: s.fecha_nacimiento_regalado || "",
    });
  }
  if (s.nombre_regalado2 || s.relacion_regalado2) {
    out.push({
      relacion: s.relacion_regalado2 || "",
      nombre: s.nombre_regalado2 || "",
      fecha: s.fecha_nacimiento_regalado2 || "",
    });
  }
  if (ed?.regalados_extra && Array.isArray(ed.regalados_extra)) {
    for (const r of ed.regalados_extra as Record<string, string>[]) {
      out.push({
        relacion: r.relacion || r.para_quien || "",
        nombre: r.nombre || r.destinatario_nombre || "",
        fecha: r.fecha || r.cual_es_su_fecha_de_nacimiento || "",
      });
    }
  }
  return out.filter((r) => r.nombre || r.relacion);
}

export type AutomationTrigger =
  // Shopify: carrito y checkout
  | "abandoned_cart" | "checkout_started" | "added_to_cart"
  // Shopify: órdenes
  | "placed_order" | "ordered_product"
  | "fulfilled_order" | "fulfilled_partial_order"
  | "confirmed_shipment" | "delivered_shipment" | "marked_out_for_delivery"
  | "cancelled_order" | "refunded_order"
  // Cupones
  | "coupon_assigned" | "coupon_used"
  // Web tracking
  | "viewed_product" | "active_on_site" | "subscribed_to_back_in_stock"
  // Internos
  | "welcome" | "post_visit" | "reactivation"
  | "birthday_reminder"
  | "form_submitted"
  | "product_of_month";
export type AutomationStatus = "active" | "paused";

export interface AutomationVariant {
  variant: string;      // "A", "B", "C", "D"
  subject: string;
  template_id: number;
  weight: number;
}

export type MondayOccurrence = "first" | "second" | "third" | "fourth" | "last";

export interface AutomationStep {
  step: number;
  delay_hours: number;
  template_id: number;
  subject: string;
  preview_text?: string;
  condition: "not_purchased" | "not_recovered" | "always" | null;
  send_on_monday?: MondayOccurrence;
  variants?: AutomationVariant[];
}

export interface Automation {
  id: number;
  name: string;
  trigger_type: string;
  trigger_config: Record<string, number> | null;
  steps: AutomationStep[] | null;
  template_id: number | null;
  subject: string | null;
  status: string;
  coupon_campaign_id: number | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface AutomationRun {
  id: number;
  automation_id: number;
  contact_id: number | null;
  contact_email: string;
  trigger_key: string;
  step_number: number;
  variant_sent: string | null;
  status: "sent" | "failed" | "skipped";
  triggered_at: string;
  executed_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
  resend_id: string | null;
  error: string | null;
}

export interface AutomationPendingContact {
  email: string;
  name: string;
  detail: string;
  send_at: string;
  ready: boolean;
  step?: number;
}

export interface AutomationPendingStep {
  step: number;
  count: number;
  contacts: AutomationPendingContact[];
}

export interface AutomationPending {
  count: number;
  steps: AutomationPendingStep[];
  will_enter: { count: number } | null;
}

export interface AutomationVariantStat {
  variant: string;
  sent: number;
  opened: number;
  clicked: number;
  conversions: number;
  open_rate: number;
  click_rate: number;
  conversion_rate: number;
}

export interface AutomationStepStat {
  step: number;
  sent: number;
  opened: number;
  clicked: number;
  open_rate: number;
  click_rate: number;
  variants: AutomationVariantStat[];
}

export interface AutomationStats {
  total: number;
  sent: number;
  failed: number;
  opened: number;
  clicked: number;
  open_rate: number;
  click_rate: number;
  orders: number;
  revenue: number;
  last_run: string | null;
  variants: AutomationVariantStat[];
}

export interface OverviewStats {
  contacts: { total: number; opted_in: number };
  campaigns: { total: number; sent: number };
  sends: { total: number; delivered: number; opened: number; open_rate: number };
  segments: number;
  templates: number;
}
