"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError, formatMoney, type Cart } from "@elton/api-client";
import { trackEvent } from "@elton/analytics";
import { Button, DeliveryNote, EmptyState, Loading, Notice, PageIntro } from "@elton/ui";

const issueText: Record<string, string> = { PRODUCT_INACTIVE: "Товар снят с публикации", PRICE_MISSING: "Цена уточняется", BUNDLE_INVALID: "Комплект требует обновления", CALCULATION_OVERFLOW: "Количество или сумма требует исправления" };

export default function CartClient() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  async function load() { try { setCart(await api.cart()); setError(null); } catch (reason) { setError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true })); } }
  useEffect(() => { void load(); }, []);
  async function update(productId: string, quantity: number) { if (!cart) return; setBusy(productId); try { setCart(await api.setQuantity(productId, quantity, cart.version)); } catch (reason) { setError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true })); } finally { setBusy(null); } }
  async function remove(productId: string) { if (!cart) return; setBusy(productId); try { setCart(await api.removeLine(productId, cart.version)); trackEvent({ name: "remove_from_cart", product_id: productId }); } catch (reason) { setError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true })); } finally { setBusy(null); } }
  if (!cart && !error) return <><PageIntro eyebrow="Корзина" title="Ваши предметы." /><Loading /></>;
  return <><PageIntro eyebrow="Корзина" title="Ваши предметы." >Гостевая корзина сохраняется на сервере в течение текущей сессии.</PageIntro>{error && <Notice tone="warning">{error.problem.code === "CART_CHANGED" ? "Каталог изменился. Обновите корзину и проверьте строки." : `Не удалось обновить корзину. Код: ${error.problem.code ?? "STORAGE_TEMPORARILY_UNAVAILABLE"}.`}</Notice>}{cart && (cart.items.length === 0 ? <EmptyState title="Корзина пуста">Выберите предмет в <Link href="/catalog">каталоге</Link>.</EmptyState> : <div className="cart-layout"><section className="card" aria-label="Товары в корзине">{cart.items.map((line) => <div className="cart-line" key={line.product_id}><div className="cart-thumb" aria-hidden="true" /><div><strong>{line.product_id.slice(0, 8)}</strong>{line.issue && <p className="muted">{issueText[line.issue] ?? line.issue}</p>}</div><div className="quantity"><button className="button button-quiet" onClick={() => void update(line.product_id, line.quantity - 1)} disabled={Boolean(line.issue) || line.quantity <= 1 || busy === line.product_id} aria-label="Уменьшить количество">−</button><span>{line.quantity}</span><button className="button button-quiet" onClick={() => void update(line.product_id, line.quantity + 1)} disabled={Boolean(line.issue) || busy === line.product_id} aria-label="Увеличить количество">+</button></div><div className="line-total">{formatMoney(line.line_total)}<button className="button button-quiet" onClick={() => void remove(line.product_id)} disabled={busy === line.product_id}>Удалить</button></div></div>)}</section><aside className="card summary"><h2>Итого</h2><div className="summary-row"><span>Товары</span><strong>{formatMoney(cart.goods_total)}</strong></div><DeliveryNote /><div className="summary-row summary-total"><span>К оплате</span><strong>{formatMoney(cart.payable_total)}</strong></div><Link className={`button button-primary${!cart.can_quote ? " button-disabled" : ""}`} aria-disabled={!cart.can_quote} href={cart.can_quote ? "/checkout" : "/cart"} onClick={() => { if (cart.can_quote) trackEvent({ name: "begin_checkout" }); }}>Перейти к заявке</Link>{!cart.can_quote && <p className="muted">Сначала исправьте строки с ошибками.</p>}</aside></div>)}</>;
}
