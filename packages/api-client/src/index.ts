import type { components } from "./generated";

export type Money = components["schemas"]["Money"];
export type ProductSummary = components["schemas"]["ProductSummary"];
export type ProductDetail = components["schemas"]["ProductDetail"];
export type Category = components["schemas"]["CategoryDTO"];
export type ProductPage = components["schemas"]["ProductPage"];
export type Cart = components["schemas"]["CartDTO"];
export type CartLine = components["schemas"]["CartLine"];
export type DraftQuote = components["schemas"]["DraftQuoteDTO"];
export type Draft = components["schemas"]["DraftDTO"];
export type Contact = components["schemas"]["ContactDemo"];
export type Address = components["schemas"]["AddressDemo"];
export type Capabilities = components["schemas"]["CapabilitiesDTO"];
export type AdminDraftPage = components["schemas"]["DraftPageDTO"];
export type AdminDraft = components["schemas"]["AdminDraftDTO"];
export type AdminProduct = components["schemas"]["ProductAdminDTO"];
export type AdminProductPage = components["schemas"]["ProductAdminPageDTO"];
export type AdminProductCreate = components["schemas"]["ProductCreateDTO"];
export type AdminProductWrite = components["schemas"]["ProductWriteDTO"];
export type AdminSitePriceWrite = components["schemas"]["SitePriceWriteDTO"];
export type AdminBundleWrite = components["schemas"]["BundleWriteDTO"];
export type AdminBundle = components["schemas"]["BundleAdminDTO"];
export type AdminMedia = components["schemas"]["MediaDTO"];
export type AdminSession = components["schemas"]["AdminSessionDTO"];
export type AdminLogin = components["schemas"]["AdminLoginDTO"];

export interface Problem {
  type?: string;
  title?: string;
  status?: number;
  code?: string;
  detail?: string;
  trace_id?: string;
  retryable?: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem;
  readonly retryable: boolean;

  constructor(status: number, problem: Problem, message = "Не удалось выполнить запрос") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
    this.retryable = Boolean(problem.retryable) || status === 503;
  }
}

let csrfToken: string | null = null;
let adminCsrfToken: string | null = null;

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return null;
  return parseResponseText(await response.text());
}

function parseResponseText(text: string): unknown {
  if (!text) return null;
  try { return JSON.parse(text) as unknown; } catch { return { detail: text }; }
}

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  // Let fetch add the multipart boundary. Setting application/json for FormData
  // makes the protected media endpoint reject an otherwise valid upload.
  const isMultipart = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !headers.has("Content-Type") && !isMultipart) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers, credentials: "include", cache: "no-store" });
  return response;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await raw(path, init);
  const payload = await parseResponse(response);
  if (!response.ok) {
    throw new ApiError(response.status, (payload ?? {}) as Problem);
  }
  return payload as T;
}

export async function ensureGuestSession(): Promise<{ csrf_token: string; expires_at: string }> {
  if (csrfToken) return { csrf_token: csrfToken, expires_at: "" };
  let session = await raw("/api/v1/session");
  if (session.status === 401) {
    session = await raw("/api/v1/guest-sessions", { method: "POST" });
  }
  const payload = await parseResponse(session);
  if (!session.ok) throw new ApiError(session.status, (payload ?? {}) as Problem);
  csrfToken = (payload as { csrf_token: string }).csrf_token;
  return payload as { csrf_token: string; expires_at: string };
}

async function guestRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = await ensureGuestSession();
  const headers = new Headers(init.headers);
  headers.set("X-CSRF-Token", session.csrf_token);
  return request<T>(path, { ...init, headers });
}

function rememberAdminSession(session: AdminSession): AdminSession {
  adminCsrfToken = session.csrf_token;
  return session;
}

async function adminMutation<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!adminCsrfToken) await api.adminSession();
  const headers = new Headers(init.headers);
  headers.set("X-CSRF-Token", adminCsrfToken ?? "");
  return request<T>(path, { ...init, headers });
}

type UploadProgressCallback = (percent: number) => void;

async function uploadWithProgress<T>(path: string, init: RequestInit, onProgress?: UploadProgressCallback): Promise<T> {
  // Vitest, SSR and non-browser consumers do not provide XMLHttpRequest. Keep
  // the fetch implementation as a compatible fallback for those environments.
  if (typeof XMLHttpRequest === "undefined") return adminMutation<T>(path, init);
  if (!adminCsrfToken) await api.adminSession();

  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-CSRF-Token", adminCsrfToken ?? "");

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(init.method ?? "POST", path, true);
    xhr.withCredentials = true;
    headers.forEach((value, key) => xhr.setRequestHeader(key, value));
    onProgress?.(0);
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return;
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };
    xhr.onload = () => {
      const payload = xhr.status === 204 ? null : parseResponseText(xhr.responseText);
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new ApiError(xhr.status, (payload ?? {}) as Problem));
        return;
      }
      onProgress?.(100);
      resolve(payload as T);
    };
    const rejectNetwork = () => reject(new ApiError(503, { retryable: true }));
    xhr.onerror = rejectNetwork;
    xhr.onabort = rejectNetwork;
    xhr.send(init.body as XMLHttpRequestBodyInit);
  });
}

function queryString(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return query.size ? `?${query}` : "";
}

export const api = {
  capabilities: () => request<Capabilities>("/api/v1/capabilities"),
  categories: () => request<{ items: Category[] }>("/api/v1/categories"),
  products: (params: { q?: string; category?: string; sort?: string; limit?: number } = {}) => {
    return request<ProductPage>(`/api/v1/products${queryString(params)}`);
  },
  product: (slug: string) => request<ProductDetail>(`/api/v1/products/by-slug/${encodeURIComponent(slug)}`),
  cart: () => guestRequest<Cart>("/api/v1/cart", { method: "GET" }),
  setQuantity: (productId: string, quantity: number, version: number) => guestRequest<Cart>(`/api/v1/cart/items/${productId}`, { method: "PUT", headers: { "If-Match": `"${version}"` }, body: JSON.stringify({ quantity }) }),
  removeLine: (productId: string, version: number) => guestRequest<Cart>(`/api/v1/cart/items/${productId}`, { method: "DELETE", headers: { "If-Match": `"${version}"` } }),
  quote: (cartVersion: number) => guestRequest<DraftQuote>("/api/v1/draft-quotes", { method: "POST", body: JSON.stringify({ cart_version: cartVersion }) }),
  saveDraft: (command: { quote_id: string; contact: Contact; address: Address }, idempotencyKey: string) => guestRequest<Draft>("/api/v1/checkout-drafts", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(command) }),
  draft: (id: string) => guestRequest<Draft>(`/api/v1/checkout-drafts/${encodeURIComponent(id)}`, { method: "GET" }),
  adminSession: async () => {
    try {
      return rememberAdminSession(await request<AdminSession>("/api/v1/admin/session"));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) adminCsrfToken = null;
      throw error;
    }
  },
  adminLogin: (command: AdminLogin) => request<AdminSession>("/api/v1/admin/auth/login", {
    method: "POST",
    body: JSON.stringify(command),
  }).then(rememberAdminSession),
  adminLogout: async () => {
    try {
      await adminMutation<null>("/api/v1/admin/auth/logout", { method: "POST" });
    } finally {
      adminCsrfToken = null;
    }
  },
  adminProducts: (params: { q?: string; limit?: number; cursor?: string } = {}) => request<AdminProductPage>(`/api/v1/admin/products${queryString(params)}`),
  createAdminProduct: (command: AdminProductCreate) => adminMutation<AdminProduct>("/api/v1/admin/products", {
    method: "POST",
    body: JSON.stringify(command),
  }),
  adminProduct: (productId: string) => request<AdminProduct>(`/api/v1/admin/products/${encodeURIComponent(productId)}`),
  adminBundle: (productId: string) => request<AdminBundle>(`/api/v1/admin/products/${encodeURIComponent(productId)}/bundle`),
  updateAdminProduct: (productId: string, patch: AdminProductWrite, version: number) => adminMutation<AdminProduct>(`/api/v1/admin/products/${encodeURIComponent(productId)}`, {
    method: "PATCH",
    headers: { "If-Match": `"${version}"` },
    body: JSON.stringify(patch),
  }),
  setAdminSitePrice: (productId: string, command: AdminSitePriceWrite, version: number) => adminMutation<AdminProduct>(`/api/v1/admin/products/${encodeURIComponent(productId)}/site-price`, {
    method: "PUT",
    headers: { "If-Match": `"${version}"` },
    body: JSON.stringify(command),
  }),
  replaceAdminBundle: (productId: string, command: AdminBundleWrite, version: number) => adminMutation<AdminBundle>(`/api/v1/admin/products/${encodeURIComponent(productId)}/bundle`, {
    method: "PUT",
    headers: { "If-Match": `"${version}"` },
    body: JSON.stringify(command),
  }),
  uploadAdminMedia: (productId: string, file: Blob, metadata: { alt_text?: string; position?: number } = {}, version: number, filename?: string, onProgress?: UploadProgressCallback) => {
    const form = new FormData();
    const inferredName = filename ?? ("name" in file && typeof file.name === "string" ? file.name : "upload");
    form.append("file", file, inferredName);
    if (metadata.alt_text !== undefined) form.append("alt_text", metadata.alt_text);
    if (metadata.position !== undefined) form.append("position", String(metadata.position));
    return uploadWithProgress<AdminMedia>(`/api/v1/admin/products/${encodeURIComponent(productId)}/media`, {
      method: "POST",
      headers: { "If-Match": `"${version}"` },
      body: form,
    }, onProgress);
  },
  deleteAdminMedia: (productId: string, mediaId: string, version: number) => adminMutation<null>(`/api/v1/admin/products/${encodeURIComponent(productId)}/media/${encodeURIComponent(mediaId)}`, {
    method: "DELETE",
    headers: { "If-Match": `"${version}"` },
  }),
  adminDrafts: (params: { cursor?: string; created_from?: string; created_to?: string } = {}) => request<AdminDraftPage>(`/api/v1/admin/checkout-drafts${queryString(params)}`),
  adminDraft: (draftId: string) => request<AdminDraft>(`/api/v1/admin/checkout-drafts/${encodeURIComponent(draftId)}`),
};

export function resetSessionForUnauthorized() { csrfToken = null; }
export function resetAdminSessionForUnauthorized() { adminCsrfToken = null; }

export function formatMoney(money: Money | null | undefined): string {
  if (!money) return "Цена уточняется";
  const minor = BigInt(money.amount_minor);
  const major = minor / 100n;
  const cents = (minor % 100n).toString().padStart(2, "0");
  return `${major.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ")},${cents} ₽`;
}
