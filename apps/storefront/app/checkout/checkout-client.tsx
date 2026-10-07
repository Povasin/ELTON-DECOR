"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api, ApiError, formatMoney, type Address, type Cart, type Contact, type DraftQuote } from "@elton/api-client";
import { Button, Card, DeliveryNote, Loading, Notice, PageIntro } from "@elton/ui";

type Pending = { created_at: number; key: string; command: { quote_id: string; contact: Contact; address: Address } };
const PENDING_KEY = "elton.checkout.pending.v1";
const MAX_PENDING_AGE_MS = 60 * 60 * 1000;
const MAX_PENDING_BYTES = 16 * 1024;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function text(value: unknown, max: number, required = false): value is string {
  return typeof value === "string" && value.length <= max && (!required || value.length > 0);
}

function validOptionalText(value: unknown, max: number): value is string | null | undefined {
  return value === null || value === undefined || text(value, max);
}

function validPendingShape(value: unknown): value is Pending {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Pending> & { command?: { quote_id?: unknown; contact?: unknown; address?: unknown } };
  if (!Number.isInteger(candidate.created_at) || !UUID.test(candidate.key ?? "") || !candidate.command || !UUID.test(String(candidate.command.quote_id ?? ""))) return false;
  const contact = candidate.command.contact;
  const address = candidate.command.address;
  if (!contact || typeof contact !== "object" || !address || typeof address !== "object") return false;
  const contactValue = contact as Record<string, unknown>;
  const addressValue = address as Record<string, unknown>;
  return text(contactValue.phone, 32, true) && validOptionalText(contactValue.name, 120) && validOptionalText(contactValue.email, 254) && text(addressValue.city, 120, true) && text(addressValue.address_line, 500, true) && validOptionalText(addressValue.postal_code, 20);
}

function byteLength(value: string): number { return new TextEncoder().encode(value).byteLength; }

function pending(): Pending | null {
  try {
    const value = sessionStorage.getItem(PENDING_KEY);
    if (!value || byteLength(value) > MAX_PENDING_BYTES) { if (value) sessionStorage.removeItem(PENDING_KEY); return null; }
    const parsed: unknown = JSON.parse(value);
    const age = validPendingShape(parsed) ? Date.now() - parsed.created_at : Number.POSITIVE_INFINITY;
    if (!validPendingShape(parsed) || age < 0 || age >= MAX_PENDING_AGE_MS) { sessionStorage.removeItem(PENDING_KEY); return null; }
    return parsed;
  } catch { try { sessionStorage.removeItem(PENDING_KEY); } catch { /* storage can be unavailable */ } return null; }
}
function setPending(value: Pending | null) {
  try {
    if (!value) { sessionStorage.removeItem(PENDING_KEY); return; }
    const serialized = JSON.stringify(value);
    if (byteLength(serialized) > MAX_PENDING_BYTES || !validPendingShape(value)) { sessionStorage.removeItem(PENDING_KEY); return; }
    sessionStorage.setItem(PENDING_KEY, serialized);
  } catch { /* private browsing can deny storage */ }
}

export default function CheckoutClient() {
  const [cart, setCart] = useState<Cart | null>(null); const [quote, setQuote] = useState<DraftQuote | null>(null); const [error, setError] = useState<ApiError | null>(null); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [savedId, setSavedId] = useState<string | null>(null);
  const [contact, setContact] = useState<Contact>({ phone: "", name: null, email: null }); const [address, setAddress] = useState<Address>({ city: "", address_line: "", postal_code: null });
  useEffect(() => { void api.cart().then(async (value) => { setCart(value); if (!value.can_quote) return; setQuote(await api.quote(value.version)); }).catch((reason: unknown) => setError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true }))).finally(() => setLoading(false)); }, []);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!quote) return; const existing = pending(); const command = existing?.command ?? { quote_id: quote.quote_id, contact: { ...contact, name: contact.name || null, email: contact.email || null }, address: { ...address, postal_code: address.postal_code || null } }; const key = existing?.key ?? crypto.randomUUID(); setPending({ created_at: Date.now(), key, command }); setSaving(true); setError(null); try { const saved = await api.saveDraft(command, key); setPending(null); setSavedId(saved.id); } catch (reason) { const apiError = reason instanceof ApiError ? reason : new ApiError(503, { retryable: true }); setError(apiError); if (!apiError.retryable) setPending(null); } finally { setSaving(false); } }
  if (savedId) return <><PageIntro eyebrow="Заявка сохранена" title="Спасибо, мы получили заявку." /><Notice tone="success">Заявка сохранена; оплата и доставка пока не подключены</Notice><Link className="button button-primary" href={`/result/${savedId}`}>Открыть результат</Link></>;
  if (loading) return <><PageIntro eyebrow="Заявка" title="Проверяем корзину." /><Loading /></>;
  if (!cart?.can_quote || !quote) return <><PageIntro eyebrow="Заявка" title="Нужен действительный состав." /><Notice tone="warning">В корзине есть строки, которые нужно исправить перед сохранением заявки.</Notice><Link className="button button-primary" href="/cart">Вернуться в корзину</Link></>;
  return <><PageIntro eyebrow="Локальная заявка" title="Оставьте контакты." >Это демонстрационный этап: мы сохраняем состав и контактные данные, без оплаты и выбора доставки.</PageIntro>{error && <Notice tone="warning">{error.problem.code === "QUOTE_CHANGED" ? "Каталог изменился. Вернитесь в корзину и создайте новую заявку." : error.problem.code === "QUOTE_EXPIRED" ? "Срок проверки истёк. Создайте заявку заново." : `Не удалось сохранить заявку. Код: ${error.problem.code ?? "STORAGE_TEMPORARILY_UNAVAILABLE"}.`}</Notice>}<div className="cart-layout"><form className="card" onSubmit={submit}><h2>Контакты и адрес</h2><div className="form-grid"><label className="field field-full">Телефон<input required maxLength={32} value={contact.phone} onChange={(event) => setContact({ ...contact, phone: event.target.value })} autoComplete="tel" /></label><label className="field">Имя<input maxLength={120} value={contact.name ?? ""} onChange={(event) => setContact({ ...contact, name: event.target.value })} autoComplete="name" /></label><label className="field">Email<input type="email" maxLength={254} value={contact.email ?? ""} onChange={(event) => setContact({ ...contact, email: event.target.value })} autoComplete="email" /></label><label className="field">Город<input required maxLength={120} value={address.city} onChange={(event) => setAddress({ ...address, city: event.target.value })} autoComplete="address-level2" /></label><label className="field">Индекс<input maxLength={20} value={address.postal_code ?? ""} onChange={(event) => setAddress({ ...address, postal_code: event.target.value })} autoComplete="postal-code" /></label><label className="field field-full">Адрес<input required maxLength={500} value={address.address_line} onChange={(event) => setAddress({ ...address, address_line: event.target.value })} autoComplete="street-address" /></label></div><Button type="submit" disabled={saving}>{saving ? "Сохраняем…" : "Сохранить заявку"}</Button><p className="muted">Состав заявки фиксируется сервером. Транспортный повтор использует тот же ключ только в текущей сессии браузера.</p></form><aside className="card summary"><h2>Состав</h2>{quote.items.map((item) => <div className="summary-row" key={item.product_id}><span>{item.title} × {item.quantity}</span><strong>{formatMoney(item.line_total)}</strong></div>)}<div className="summary-row summary-total"><span>Товары</span><strong>{formatMoney(quote.goods_total)}</strong></div><DeliveryNote /><div className="summary-row"><span>К оплате</span><strong>{formatMoney(quote.payable_total)}</strong></div></aside></div></>;
}
