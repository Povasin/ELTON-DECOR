"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, formatMoney, request, type AdminDraftPage, type Money } from "@elton/api-client";
import { Card, Notice } from "@elton/ui";
import { AdminAccess } from "../../../components/admin-access";

type SnapshotComponent = {
  product_id?: unknown;
  sku?: unknown;
  title?: unknown;
  quantity_per_bundle?: unknown;
  total_quantity?: unknown;
  base_unit_price?: MoneyLike | null;
};

type SnapshotItem = {
  product_id?: unknown;
  sku?: unknown;
  title?: unknown;
  quantity?: unknown;
  unit_price?: MoneyLike | null;
  line_total?: MoneyLike | null;
  components?: SnapshotComponent[];
};

type MoneyLike = { amount_minor?: unknown; currency?: unknown };

type AdminDraftDetail = AdminDraftPage["items"][number] & {
  items?: SnapshotItem[];
  payable_total?: MoneyLike | null;
  delivery?: { state?: unknown; amount?: MoneyLike | null } | null;
};

function text(value: unknown, fallback = "Не указано"): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function positiveInteger(value: unknown): string {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? String(value) : "—";
}

function money(value: MoneyLike | null | undefined): string {
  if (!value || typeof value.amount_minor !== "string") return "Не указано";
  try {
    return formatMoney({ amount_minor: value.amount_minor, currency: value.currency === "RUB" ? "RUB" : "RUB" });
  } catch {
    return "Не указано";
  }
}

function Snapshot({ items }: { items: SnapshotItem[] | undefined }) {
  if (!items?.length) {
    return <p className="muted">Снимок состава отсутствует в текущем ответе API.</p>;
  }

  return <div className="table-wrap"><table><thead><tr><th>Товар</th><th>SKU</th><th>Количество</th><th>Цена</th><th>Сумма</th></tr></thead><tbody>{items.map((item, index) => <tr key={`${text(item.product_id, "item")}-${index}`}><td>{text(item.title)}</td><td>{text(item.sku)}</td><td>{positiveInteger(item.quantity)}</td><td>{money(item.unit_price)}</td><td>{money(item.line_total)}</td></tr>)}</tbody></table>{items.some((item) => item.components?.length) && <div className="draft-components"><h3>Состав комплектов</h3>{items.filter((item) => item.components?.length).map((item, index) => <div key={`${text(item.product_id, "bundle")}-components-${index}`}><p><strong>{text(item.title)}</strong></p><ul>{item.components?.map((component, componentIndex) => <li key={`${text(component.product_id, "component")}-${componentIndex}`}>{text(component.title)} · {text(component.sku)} · {positiveInteger(component.total_quantity)} шт. · {money(component.base_unit_price)}</li>)}</ul></div>)}</div>}</div>;
}

function ContactDetails({ draft }: { draft: AdminDraftDetail }) {
  const contact = draft.contact ?? {};
  const address = draft.address ?? {};
  return <div className="admin-grid"><div><h3>Контакт</h3><dl><div><dt className="muted">Имя</dt><dd>{text(contact.name)}</dd></div><div><dt className="muted">Телефон</dt><dd>{text(contact.phone)}</dd></div><div><dt className="muted">Email</dt><dd>{text(contact.email)}</dd></div></dl></div><div><h3>Адрес</h3><dl><div><dt className="muted">Город</dt><dd>{text(address.city)}</dd></div><div><dt className="muted">Адрес</dt><dd>{text(address.address_line)}</dd></div><div><dt className="muted">Индекс</dt><dd>{text(address.postal_code)}</dd></div></dl></div></div>;
}

function DraftDetail() {
  const { id } = useParams<{ id: string }>();
  const [draft, setDraft] = useState<AdminDraftDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (!id) return;
    void request<AdminDraftDetail>(`/api/v1/admin/checkout-drafts/${encodeURIComponent(id)}`)
      .then(setDraft)
      .catch((reason: unknown) => setError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true })));
  }, [id]);

  if (error) return <><Link href="/drafts" className="muted">← К заявкам</Link><Card><Notice tone="warning">Не удалось загрузить детали заявки. Код: {error.problem.code ?? (error.status === 404 ? "NOT_FOUND" : "ADMIN_DRAFT_UNAVAILABLE")}.</Notice></Card></>;
  if (!draft) return <Card><p className="muted" role="status">Загружаем защищённые детали заявки…</p></Card>;

  return <><Link href="/drafts" className="muted">← К заявкам</Link><p className="muted">Заявка · защищённый scope drafts.read</p><h1>Детали заявки</h1><Card><div className="draft-summary"><div><span className="muted">Состояние</span><strong><span className="status-pill">{text(draft.state)}</span></strong></div><div><span className="muted">Канал</span><strong>{text(draft.channel)}</strong></div><div><span className="muted">Создана</span><strong>{new Date(draft.created_at).toLocaleString("ru-RU")}</strong></div><div><span className="muted">Товары</span><strong>{money(draft.goods_total)}</strong></div></div></Card><Card><h2>Снимок состава</h2><Snapshot items={draft.items} /></Card><Card><h2>Контакт и адрес</h2><ContactDetails draft={draft} /></Card><Card><h2>Оплата и доставка</h2><p className="muted">Оплата и доставка на этапе 1 не подключены.</p><dl><div><dt className="muted">Доставка</dt><dd>{text(draft.delivery?.state, "Не подключена")}</dd></div><div><dt className="muted">К оплате</dt><dd>{money(draft.payable_total)}</dd></div></dl></Card></>;
}

export default function DraftDetailPage() {
  return <AdminAccess><DraftDetail /></AdminAccess>;
}
