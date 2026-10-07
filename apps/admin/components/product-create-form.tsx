"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, request, type AdminProduct, type Money } from "@elton/api-client";
import { Button, Card, Loading, Notice } from "@elton/ui";
import { formatPriceInput, parseRublesToMinor } from "../lib/price";
import { attributesFromRows, type AttributeRow } from "../lib/product-form";
import { isProductVersionConflict, recoverProductConflict, saveProductDraft, type ProductSaveCommand } from "../lib/product-save";
import { ProductMedia, useMediaDraft } from "./product-media";

export type CreateProductCommand = {
  sku: string;
  title: string;
  description: string;
  type: "single" | "bundle";
  active: boolean;
  attributes: Record<string, string>;
  related_product_ids: string[];
  price: Money;
  original_price: Money | null;
};

type AdminCreateApi = typeof api & {
  createAdminProduct?: (command: CreateProductCommand) => Promise<AdminProduct>;
};

const createApi = api as AdminCreateApi;

function asApiError(reason: unknown): ApiError {
  return reason instanceof ApiError ? reason : new ApiError(503, { retryable: true });
}

function errorText(error: ApiError): string {
  if (error.problem.code === "CAPABILITY_DISABLED" || error.problem.detail === "CAPABILITY_DISABLED") return "Загрузка этого типа медиа пока недоступна на сервере. Файл оставлен в форме.";
  if (error.status === 409) return "Товар с таким SKU уже существует или данные изменились.";
  if (error.status === 403) return "У текущей учётной записи нет разрешения на создание товара.";
  if (error.status === 422) return "Сервер отклонил данные. Проверьте SKU, цены и характеристики.";
  if (error.status === 401) return "Сессия администратора истекла. Войдите снова.";
  return "Не удалось создать товар. Повторите попытку позже.";
}

async function createProduct(command: CreateProductCommand): Promise<AdminProduct> {
  if (createApi.createAdminProduct) return createApi.createAdminProduct(command);
  // Keep the UI usable while an older generated client is being regenerated.
  // The request still goes through the same admin API proxy and session.
  const session = await api.adminSession();
  return request<AdminProduct>("/api/v1/admin/products", {
    method: "POST",
    headers: { "X-CSRF-Token": session.csrf_token },
    body: JSON.stringify(command),
  });
}

export function ProductCreateForm() {
  const router = useRouter();
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [title, setTitle] = useState("");
  const [sku, setSku] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<"single" | "bundle">("single");
  const [active, setActive] = useState(false);
  const [priceRubles, setPriceRubles] = useState("");
  const [originalPriceRubles, setOriginalPriceRubles] = useState("");
  const [attributes, setAttributes] = useState<AttributeRow[]>([]);
  const [relatedProductIds, setRelatedProductIds] = useState<string[]>([]);
  const mediaDraft = useMediaDraft();
  const [savedProduct, setSavedProduct] = useState<AdminProduct | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadKind, setUploadKind] = useState<"image" | "video" | null>(null);
  const [busy, setBusy] = useState(false);
  const [conflictNeedsReload, setConflictNeedsReload] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nextAttributeId, setNextAttributeId] = useState(1);

  useEffect(() => {
    let mounted = true;
    void api.adminProducts().then((page) => {
      if (mounted) setProducts(page.items);
    }).catch(() => undefined).finally(() => {
      if (mounted) setLoadingProducts(false);
    });
    return () => { mounted = false; };
  }, []);

  function addAttribute() {
    setAttributes((current) => [...current, { id: nextAttributeId, name: "", value: "" }]);
    setNextAttributeId((current) => current + 1);
  }

  function updateAttribute(id: number, field: "name" | "value", value: string) {
    setAttributes((current) => current.map((row) => row.id === id ? { ...row, [field]: value } : row));
  }

  function toggleRelated(productId: string) {
    setRelatedProductIds((current) => current.includes(productId) ? current.filter((id) => id !== productId) : [...current, productId]);
  }

  function applyAuthoritative(product: AdminProduct) {
    setSavedProduct(product);
    setTitle(product.title);
    setSku(product.sku);
    setType(product.type);
    setDescription(product.description);
    setActive(product.active);
    const rows = Object.entries(product.attributes ?? {}).map(([name, value], index) => ({ id: index + 1, name, value: String(value ?? "") }));
    setAttributes(rows);
    setNextAttributeId(rows.length + 1);
    setRelatedProductIds(product.related_product_ids ?? []);
    setPriceRubles(formatPriceInput(product.price?.amount_minor ?? ""));
    setOriginalPriceRubles(formatPriceInput(product.original_price?.amount_minor ?? ""));
    setConflictNeedsReload(false);
  }

  async function reloadConflict() {
    if (!savedProduct) return;
    const recovered = await recoverProductConflict(savedProduct.id, api.adminProduct, applyAuthoritative, mediaDraft.reset);
    setError(recovered ? "Загружена актуальная карточка. Проверьте данные и повторно внесите нужные изменения." : "Не удалось загрузить актуальную карточку. Сохранение заблокировано; повторите загрузку.");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || conflictNeedsReload) return;
    setError(null);
    const cleanSku = sku.trim();
    const cleanTitle = title.trim();
    if (!cleanSku || !cleanTitle) {
      setError("Заполните название и SKU.");
      return;
    }
    const actualMinor = parseRublesToMinor(priceRubles);
    if (actualMinor === null || BigInt(actualMinor) <= 0n) {
      setError("Введите действительную цену в рублях: например, 150 или 150,50.");
      return;
    }
    const originalMinor = originalPriceRubles.trim() ? parseRublesToMinor(originalPriceRubles) : null;
    if (originalPriceRubles.trim() && (originalMinor === null || BigInt(originalMinor) <= 0n)) {
      setError("Введите корректную цену до скидки или оставьте поле пустым.");
      return;
    }
    if (originalMinor !== null && BigInt(originalMinor) < BigInt(actualMinor)) {
      setError("Цена до скидки должна быть не меньше действительной цены.");
      return;
    }
    const command: CreateProductCommand = {
      sku: cleanSku,
      title: cleanTitle,
      description,
      type,
      active,
      attributes: attributesFromRows(attributes),
      related_product_ids: relatedProductIds,
      price: { amount_minor: actualMinor, currency: "RUB" },
      original_price: originalMinor === null ? null : { amount_minor: originalMinor, currency: "RUB" },
    };
    setBusy(true);
    let targetProduct = savedProduct;
    try {
      const created = savedProduct ?? await createProduct(command);
      targetProduct = created;
      setSavedProduct(created);
      const commands: ProductSaveCommand<AdminProduct>[] = savedProduct ? [
        { run: (current) => api.updateAdminProduct(current.id, { title: command.title, description: command.description, active: command.active, attributes: command.attributes, related_product_ids: command.related_product_ids }, current.version) },
        { run: (current) => api.setAdminSitePrice(current.id, { price: command.price, original_price: command.original_price }, current.version) },
      ] : [];
      await saveProductDraft({
        product: created, commands, additions: mediaDraft.additions, removals: mediaDraft.removals,
        api: {
          read: api.adminProduct,
          remove: api.deleteAdminMedia,
          upload: (productId, addition, position, version) => {
            setUploadKind(addition.type);
            setUploadProgress(0);
            return api.uploadAdminMedia(productId, addition.file, { alt_text: "", position }, version, addition.filename, setUploadProgress);
          },
        },
        onProduct: setSavedProduct, onAdditionSaved: mediaDraft.discard, onRemovalSaved: mediaDraft.removalSaved,
      });
      router.push(`/products/${created.id}`);
    } catch (reason) {
      if (targetProduct && isProductVersionConflict(asApiError(reason))) {
        setConflictNeedsReload(true);
        const recovered = await recoverProductConflict(targetProduct.id, api.adminProduct, applyAuthoritative, mediaDraft.reset);
        setError(recovered
          ? "Данные изменились в другой вкладке. Загружена актуальная карточка, несохранённый черновик сброшен. Проверьте данные и заново внесите нужные изменения перед сохранением."
          : "Данные изменились в другой вкладке. Не удалось загрузить актуальную карточку; черновик и локальные файлы сохранены, сохранение заблокировано. Загрузите товар заново. Черновик будет сброшен только после успешной загрузки.");
        return;
      }
      setError(`${savedProduct ? "Товар создан, но сохранение не завершено. Оставшиеся изменения сохранены в форме. " : "Сохранение не завершено. Если карточка уже создана, повторное сохранение продолжит работу с ней. "}${errorText(asApiError(reason))}`);
    } finally {
      setBusy(false);
      setUploadProgress(null);
      setUploadKind(null);
    }
  }

  return <>
    <div className="admin-editor-heading"><div><p className="muted">Catalog · protected scope catalog.write</p><h1>Новый товар</h1><p className="muted">Заполните карточку, цену и медиа. После создания SKU изменить нельзя.</p></div><Button variant="secondary" onClick={() => router.push("/products")}>← К товарам</Button></div>
    {error && <Notice tone="warning"><span role="alert">{error}</span>{conflictNeedsReload && <button type="button" className="link-button" onClick={() => void reloadConflict()}>Загрузить заново</button>}</Notice>}
    <form onSubmit={(event) => void submit(event)}><fieldset className="editor-fieldset" disabled={busy || conflictNeedsReload}>
      <Card><h2>Основные данные</h2><div className="admin-editor-form"><label>Название<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={300} required /></label><label>SKU<input value={sku} onChange={(event) => setSku(event.target.value)} maxLength={100} required autoCapitalize="characters" readOnly={savedProduct !== null} /><span className="muted">SKU задаётся один раз и станет недоступен для редактирования после создания.</span></label><label>Тип товара<select disabled={savedProduct !== null} value={type} onChange={(event) => setType(event.target.value as "single" | "bundle")}><option value="single">Обычный товар</option><option value="bundle">Комплект</option></select></label><label>Описание<textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={10000} rows={6} /></label><label className="checkbox-label"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} /> Опубликовать на сайте</label></div></Card>
      <Card><div className="editor-section-heading"><div><h2>Характеристики</h2><p className="muted">Добавьте пары «название — значение», которые увидит покупатель.</p></div><Button type="button" variant="secondary" onClick={addAttribute}>Добавить характеристику</Button></div>{attributes.length ? <div className="attribute-editor-list">{attributes.map((row) => <div className="attribute-editor-row" key={row.id}><label>Название характеристики<input value={row.name} onChange={(event) => updateAttribute(row.id, "name", event.target.value)} placeholder="Материал" /></label><label>Значение<input value={row.value} onChange={(event) => updateAttribute(row.id, "value", event.target.value)} placeholder="Керамика" /></label><button type="button" className="button button-secondary" onClick={() => setAttributes((current) => current.filter((item) => item.id !== row.id))}>Удалить</button></div>)}</div> : <p className="muted">Характеристики ещё не добавлены.</p>}</Card>
      <Card><h2>Цена сайта</h2><p className="muted">Все суммы вводятся в рублях. Цена до скидки будет показана у покупателя зачёркнутой.</p><div className="admin-editor-form"><label>Цена на сайте, ₽<input inputMode="decimal" value={priceRubles} onChange={(event) => setPriceRubles(event.target.value)} placeholder="Например, 150 или 150,50" required /></label><label>Цена до скидки, ₽ <span className="muted">необязательно</span><input inputMode="decimal" value={originalPriceRubles} onChange={(event) => setOriginalPriceRubles(event.target.value)} placeholder="Например, 200" /></label></div></Card>
      <Card><div className="editor-section-heading"><div><h2>Варианты товара</h2><p className="muted">Выберите карточки одной группы, например варианты цвета. Покупатель сможет переключаться между ними в карточке товара.</p></div></div>{loadingProducts ? <Loading label="Загружаем товары…" /> : products.length ? <div className="related-product-list">{products.map((product) => <label className="related-product-option" key={product.id}><input type="checkbox" checked={relatedProductIds.includes(product.id)} onChange={() => toggleRelated(product.id)} /><span><strong>{product.title}</strong><small>{product.sku}</small></span></label>)}</div> : <p className="muted">Других товаров пока нет.</p>}</Card>
      <ProductMedia title={title} media={savedProduct?.media} draft={mediaDraft} busy={busy || conflictNeedsReload} uploadProgress={uploadProgress} uploadKind={uploadKind} />
      <div className="editor-submit-row"><Button type="submit" disabled={busy || conflictNeedsReload}>{busy ? "Сохраняем…" : "Сохранить"}</Button></div>
    </fieldset></form>
  </>;
}
