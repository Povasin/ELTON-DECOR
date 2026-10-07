"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { trackEvent } from "@elton/analytics";
import { api, ApiError, formatMoney, type Category, type ProductSummary } from "@elton/api-client";
import { AvailabilityNote, EmptyState, Loading, Notice, PageIntro } from "@elton/ui";
import { getOriginalPrice, isDiscounted, type ProductSummaryWithCatalogFields } from "../../lib/product-fields";
import { catalogQuery, catalogSearchMessage, catalogSorts, type CatalogSort } from "../../lib/catalog-query";

function CatalogProductImage({ product }: { product: ProductSummary }) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(product.thumbnail?.url) && !failed;
  return <div className={`product-image${showImage ? " has-media" : ""}`}>
    {showImage
      ? <img className="product-image-media" src={product.thumbnail!.url} alt={product.title} loading="lazy" onError={() => setFailed(true)} />
      : <span role="img" aria-label={`Иллюстрация товара ${product.title}`} />}
  </div>;
}

export default function CatalogClient({ initialCategory = "", initialQuery = "", initialSort = "title_asc" }: { initialCategory?: string; initialQuery?: string; initialSort?: CatalogSort }) {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState(initialCategory);
  const [query, setQuery] = useState(initialQuery);
  const [submittedQuery, setSubmittedQuery] = useState(initialQuery);
  const [sort, setSort] = useState<CatalogSort>(initialSort);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const router = useRouter();

  useEffect(() => { setCategory(initialCategory); setQuery(initialQuery); setSubmittedQuery(initialQuery); setSort(initialSort); }, [initialCategory, initialQuery, initialSort]);
  useEffect(() => { const request = catalogQuery({ query: submittedQuery, category, sort }); void Promise.all([api.products(request), api.categories()]).then(([page, categoryPage]) => { setProducts(page.items); setCategories(categoryPage.items); setError(null); }).catch((reason: unknown) => setError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true }))).finally(() => setLoading(false)); }, [category, sort, submittedQuery]);

  function updateUrl(next: { category?: string; query?: string; sort?: CatalogSort }) {
    const params = new URLSearchParams();
    if (next.category) params.set("category", next.category);
    if (next.query) params.set("q", next.query);
    if (next.sort && next.sort !== "title_asc") params.set("sort", next.sort);
    router.replace(`/catalog${params.size ? `?${params}` : ""}`, { scroll: false });
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    setSubmittedQuery(value);
    updateUrl({ category, query: value, sort });
    if (value) trackEvent({ name: "search", query: value, category: category || undefined });
  }

  function selectCategory(value: string) { setCategory(value); updateUrl({ category: value, query: submittedQuery, sort }); trackEvent({ name: "view_category", category: value || "all" }); }
  function selectSort(value: CatalogSort) { setSort(value); updateUrl({ category, query: submittedQuery, sort: value }); }

  return <><PageIntro eyebrow="Каталог" title="Предметы для своего ритма.">Выбирайте по форме и настроению. Наличие пока отображается как неизвестное: источник складских данных ещё не подключён.</PageIntro><form className="catalog-controls" onSubmit={submitSearch}><label className="field catalog-search">Поиск по названию или SKU<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Например, ваза" maxLength={120} /></label><button className="button button-primary" type="submit">Найти</button><label className="field catalog-sort">Сортировка<select value={sort} onChange={(event) => selectSort(event.target.value as CatalogSort)}>{catalogSorts.map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></label></form><div className="section-head"><div className="category-tabs" role="group" aria-label="Фильтр по категории"><button className={`button button-${category ? "secondary" : "primary"}`} onClick={() => selectCategory("")}>Все</button>{categories.map((item) => <button key={item.id} className={`button button-${category === item.slug ? "primary" : "secondary"}`} onClick={() => selectCategory(item.slug)}>{item.title}</button>)}</div></div>{loading ? <Loading /> : error ? <Notice tone="warning">Каталог временно недоступен. Код: {error.problem.code ?? "STORAGE_TEMPORARILY_UNAVAILABLE"}.</Notice> : products.length === 0 ? <EmptyState title="Ничего не найдено">{catalogSearchMessage(submittedQuery)}</EmptyState> : <div className="grid">{products.map((product) => {
    const catalogProduct = product as ProductSummaryWithCatalogFields;
    const originalPrice = getOriginalPrice(catalogProduct);
    const discounted = isDiscounted(catalogProduct);
    return <Link href={`/products/${product.slug}`} key={product.id} className="product-card"><CatalogProductImage product={product} /><div className="product-copy"><h3>{product.title}</h3><p>{product.type === "bundle" ? "Комплект" : "Декор для дома"}</p><AvailabilityNote /><div className="price-line"><span className="price-stack">{discounted && originalPrice && <del className="price-original">{formatMoney(originalPrice)}</del>}<strong>{formatMoney(product.price)}</strong></span><span aria-hidden="true">↗</span></div></div></Link>;
  })}</div>}</>;
}
