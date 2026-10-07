export const CLIENT_EVENT_NAMES = ["page_view", "view_category", "view_product", "search", "add_to_cart", "remove_from_cart", "begin_checkout"] as const;
export type ClientEventName = (typeof CLIENT_EVENT_NAMES)[number];

export type AnalyticsEvent = {
  name: ClientEventName;
  path?: string;
  product_id?: string;
  category?: string;
  query?: string;
  quantity?: number;
};

export function sanitizeAnalyticsEvent(value: Record<string, unknown>): AnalyticsEvent | null {
  if (!CLIENT_EVENT_NAMES.includes(value.name as ClientEventName)) return null;
  const event: AnalyticsEvent = { name: value.name as ClientEventName };
  if (typeof value.path === "string" && value.path.length <= 500) event.path = value.path;
  if (typeof value.product_id === "string" && value.product_id.length <= 64) event.product_id = value.product_id;
  if (typeof value.category === "string" && value.category.length <= 128) event.category = value.category;
  if (typeof value.query === "string" && value.query.trim().length <= 120) event.query = value.query.trim();
  if (Number.isInteger(value.quantity) && Number(value.quantity) > 0 && Number(value.quantity) <= 999) event.quantity = Number(value.quantity);
  return event;
}

export function trackEvent(value: Record<string, unknown>) {
  const event = sanitizeAnalyticsEvent(value);
  if (event && typeof window !== "undefined") window.dispatchEvent(new CustomEvent<AnalyticsEvent>("elton:analytics", { detail: event }));
  return event;
}
