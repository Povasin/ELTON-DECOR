"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, api, type AdminDraftPage } from "@elton/api-client";
import { Card, Notice } from "@elton/ui";
import { AdminAccess } from "../../components/admin-access";

function Drafts() { const [drafts, setDrafts] = useState<AdminDraftPage | null>(null); const [error, setError] = useState<ApiError | null>(null); useEffect(() => { void api.adminDrafts().then(setDrafts).catch((reason: unknown) => setError(reason instanceof ApiError ? reason : new ApiError(503, {}))); }, []); return <><p className="muted">Requests · protected scope drafts.read</p><h1>Заявки</h1>{error ? <Card><Notice tone="warning">Не удалось загрузить заявки. Повторите попытку позже.</Notice></Card> : <Card><div className="table-wrap"><table><thead><tr><th>Создана</th><th>Состояние</th><th>Сумма товаров</th></tr></thead><tbody>{drafts?.items.map((draft) => <tr key={draft.id}><td><Link href={`/drafts/${draft.id}`}>{new Date(draft.created_at).toLocaleString("ru-RU")}</Link></td><td><span className="status-pill">{draft.state}</span></td><td>{draft.goods_total.amount_minor} minor</td></tr>)}</tbody></table></div></Card>}</>; }

export default function DraftsPage() { return <AdminAccess><Drafts /></AdminAccess>; }
