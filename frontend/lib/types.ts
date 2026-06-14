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

export type CampaignStatus = "draft" | "scheduled" | "sending" | "sent" | "cancelled";

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
}

export interface FormStep {
  step: number;
  title: string;
  description: string;
  fields: string[];
  button_text: string;
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
  extra_data: Record<string, string> | null;
  coupon_code: string | null;
  created_at: string;
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
  | "welcome" | "post_visit" | "reactivation" | "abandoned_booking"
  | "form_submitted";
export type AutomationStatus = "active" | "paused";

export interface AutomationVariant {
  variant: string;      // "A", "B", "C", "D"
  subject: string;
  template_id: number;
  weight: number;
}

export interface AutomationStep {
  step: number;
  delay_hours: number;
  template_id: number;
  subject: string;
  preview_text?: string;
  condition: "not_purchased" | "not_recovered" | "always" | null;
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

export interface AutomationPending {
  count: number;
  contacts: AutomationPendingContact[];
}

export interface AutomationVariantStat {
  variant: string;
  sent: number;
  opened: number;
  clicked: number;
  open_rate: number;
  click_rate: number;
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
