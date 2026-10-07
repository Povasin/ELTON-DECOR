"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, api, type AdminProduct } from "@elton/api-client";
import { Card, Notice } from "@elton/ui";
import { AdminAccess } from "../../components/admin-access";

function Products() { const [products, setProducts] = useState<AdminProduct[]>([]); const [error, setError] = useState<ApiError | null>(null); useEffect(() => { void api.adminProducts().then((page) => setProducts(page.items)).catch((reason: unknown) => setError(reason instanceof ApiError ? reason : new ApiError(503, {}))); }, []); return <><div className="admin-page-heading"><div><p className="muted">Catalog · protected scope catalog.read</p><h1>Товары</h1></div><Link className="button" href="/products/new">Добавить товар</Link></div>{error ? <Card><Notice tone="warning">Не удалось загрузить товары. Повторите попытку позже.</Notice></Card> : <Card><div className="table-wrap"><table><thead><tr><th>Название</th><th>SKU</th><th>Состояние</th></tr></thead><tbody>{products.map((product) => <tr key={product.id}><td><Link href={`/products/${product.id}`}>{product.title}</Link></td><td>{product.sku}</td><td><span className="status-pill">{product.active ? "Опубликован" : "Скрыт"}</span></td></tr>)}</tbody></table></div></Card>}</>; }

export default function ProductsPage() { return <AdminAccess><Products /></AdminAccess>; }
