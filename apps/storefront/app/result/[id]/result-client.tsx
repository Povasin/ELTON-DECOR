"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, formatMoney, type Draft } from "@elton/api-client";
import { DeliveryNote, Loading, Notice, PageIntro } from "@elton/ui";

export default function ResultClient() {
  const { id } = useParams<{ id: string }>(); const [draft, setDraft] = useState<Draft | null>(null); const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => { if (!id) return; void api.draft(id).then(setDraft).catch((reason: unknown) => setError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true }))); }, [id]);
  if (error) return <><PageIntro eyebrow="Заявка" title="Результат недоступен." /><Notice tone="warning">Мы не нашли заявку в текущей гостевой сессии. Код: {error.problem.code ?? "NOT_FOUND"}.</Notice><Link className="button button-secondary" href="/catalog">Вернуться в каталог</Link></>;
  if (!draft) return <Loading />;
  return <><PageIntro eyebrow="Заявка сохранена" title="Мы получили ваш запрос." >Номер заявки: <strong>{draft.id}</strong></PageIntro><Notice tone="success">{draft.message}</Notice><section className="card"><h2>Состав</h2>{draft.items.map((item) => <div className="summary-row" key={item.product_id}><span>{item.title} × {item.quantity}</span><strong>{formatMoney(item.line_total)}</strong></div>)}<div className="summary-row summary-total"><span>Товары</span><strong>{formatMoney(draft.goods_total)}</strong></div><DeliveryNote /><div className="summary-row"><span>К оплате</span><strong>{formatMoney(draft.payable_total)}</strong></div></section><p><Link className="button button-secondary" href="/catalog">Продолжить просмотр</Link></p></>;
}
