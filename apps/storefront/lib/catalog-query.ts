export const catalogSorts = [
  ["title_asc", "По названию"],
  ["price_asc", "Сначала дешевле"],
  ["price_desc", "Сначала дороже"],
] as const;

export type CatalogSort = (typeof catalogSorts)[number][0];

export function catalogQuery({ query = "", category = "", sort = "title_asc" }: { query?: string; category?: string; sort?: string }) {
  const resolvedSort: CatalogSort = catalogSorts.some(([value]) => value === sort) ? sort as CatalogSort : "title_asc";
  return { q: query.trim(), category, sort: resolvedSort, limit: 24 };
}

export function catalogSearchMessage(query: string) {
  const value = query.trim();
  return value
    ? `По запросу «${value}» ничего не найдено. Попробуйте изменить запрос или фильтр.`
    : "В этой категории пока нет опубликованных товаров.";
}
