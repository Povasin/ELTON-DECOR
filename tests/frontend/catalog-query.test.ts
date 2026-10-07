import { describe, expect, it } from "vitest";
import { catalogQuery, catalogSearchMessage } from "../../apps/storefront/lib/catalog-query";

describe("catalog query", () => {
  it("normalizes a text search and keeps the selected sort", () => {
    expect(catalogQuery({ query: "  ваза  ", category: "vases", sort: "price_desc" })).toEqual({
      q: "ваза",
      category: "vases",
      sort: "price_desc",
      limit: 24,
    });
  });

  it("explains an empty search result", () => {
    expect(catalogSearchMessage("ваза")).toBe("По запросу «ваза» ничего не найдено. Попробуйте изменить запрос или фильтр.");
  });
});
