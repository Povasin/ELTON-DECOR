"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ApiError, api, formatMoney, type AdminProduct, type Money } from "@elton/api-client";
import { Button, Card, Loading, Notice } from "@elton/ui";
import { formatPriceInput, parseRublesToMinor } from "../lib/price";
import { isProductVersionConflict, recoverProductConflict, saveProductDraft, type ProductSaveCommand } from "../lib/product-save";
import { ProductMedia, useMediaDraft } from "./product-media";

type AdminMedia = {
  id: string;
  type: "image" | "video";
  url: string;
  alt_text: string;
  position: number;
};

type AdminBundleComponent = {
  product_id: string;
  sku: string;
  title: string;
  quantity: number;
  base_unit_price: Money;
};

type AdminBundle = {
  version_id: string;
  version: number;
  components: AdminBundleComponent[];
};

type AdminEditorProduct = AdminProduct & {
  media?: AdminMedia[];
  bundle?: AdminBundle | null;
  original_price?: Money | null;
  related_product_ids?: string[];
};

// All editor commands use the shared Elton API client and admin session.
const editorApi = api;

type EditableComponent = {
  product_id: string;
  quantity: string;
};

type EditableAttribute = {
  id: number;
  name: string;
  value: string;
};

function asApiError(reason: unknown): ApiError {
  return reason instanceof ApiError ? reason : new ApiError(503, { retryable: true });
}

function errorText(error: ApiError, action: string): string {
  if (error.problem.code === "CAPABILITY_DISABLED" || error.problem.detail === "CAPABILITY_DISABLED") {
    return "Загрузка этого типа медиа пока отключена сервером до завершения проверки pipeline.";
  }
  if (error.status === 409 || error.problem.code === "VERSION_CONFLICT") {
    return "Эти данные уже изменились в другой вкладке. Загрузите товар заново и повторите действие.";
  }
  if (error.status === 403) return "У текущей учётной записи нет разрешения на это действие.";
  if (error.status === 401) return "Сессия администратора истекла. Войдите снова.";
  if (error.status === 422) return `Сервер отклонил ${action}. Проверьте заполненные поля.`;
  return `Не удалось ${action}. Повторите попытку позже.`;
}

function minorPrice(product: AdminEditorProduct): string {
  return product.price?.amount_minor ?? "";
}

function originalMinorPrice(product: AdminEditorProduct): string {
  return product.original_price?.amount_minor ?? "";
}

function attributeRows(attributes: Record<string, unknown> | undefined): EditableAttribute[] {
  return Object.entries(attributes ?? {}).map(([name, value], index) => ({ id: index + 1, name, value: String(value ?? "") }));
}

function attributesObject(rows: EditableAttribute[]): Record<string, string> {
  return rows.reduce<Record<string, string>>((result, row) => {
    const name = row.name.trim();
    if (name) result[name] = row.value.trim();
    return result;
  }, {});
}

function bundleRows(bundle: AdminBundle | null | undefined): EditableComponent[] {
  return (bundle?.components ?? []).map((component) => ({
    product_id: component.product_id,
    quantity: String(component.quantity),
  }));
}

export function ProductEditor() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<AdminEditorProduct | null>(null);
  const [componentProducts, setComponentProducts] = useState<AdminProduct[]>([]);
  const [components, setComponents] = useState<EditableComponent[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [active, setActive] = useState(false);
  const [attributes, setAttributes] = useState<EditableAttribute[]>([]);
  const [relatedProductIds, setRelatedProductIds] = useState<string[]>([]);
  const [nextAttributeId, setNextAttributeId] = useState(1);
  const [priceRubles, setPriceRubles] = useState("");
  const [originalPriceRubles, setOriginalPriceRubles] = useState("");
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [conflictNeedsReload, setConflictNeedsReload] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadKind, setUploadKind] = useState<"image" | "video" | null>(null);
  const loadRequestRef = useRef(0);
  const mediaDraft = useMediaDraft();

  const applyAuthoritative = useCallback((complete: AdminEditorProduct) => {
    setProduct(complete);
    setTitle(complete.title);
    setDescription(complete.description);
    setActive(complete.active);
    const loadedAttributes = attributeRows(complete.attributes);
    setAttributes(loadedAttributes);
    setNextAttributeId(loadedAttributes.reduce((max, row) => Math.max(max, row.id), 0) + 1);
    setRelatedProductIds(complete.related_product_ids ?? []);
    setPriceRubles(formatPriceInput(minorPrice(complete)));
    setOriginalPriceRubles(formatPriceInput(originalMinorPrice(complete)));
    setComponents(bundleRows(complete.bundle));
    setConflictNeedsReload(false);
  }, []);

  const load = useCallback(async () => {
    if (!id) return;
    const requestId = ++loadRequestRef.current;
    setLoadError(null);
    try {
      const loaded = editorApi.adminProduct
        ? await editorApi.adminProduct(id)
        : (await editorApi.adminProducts()).items.find((item) => item.id === id) as AdminEditorProduct | undefined;
      if (!loaded) throw new ApiError(404, { code: "NOT_FOUND" });
      const bundle = loaded.bundle ?? (loaded.type === "bundle" && editorApi.adminBundle ? await editorApi.adminBundle(id) : null);
      const complete = { ...loaded, bundle } as AdminEditorProduct;
      // React development mode and mutation refreshes can overlap. An older
      // response must not overwrite a newer product version and cause a stale
      // If-Match on the next media operation.
      if (requestId !== loadRequestRef.current) return;
      applyAuthoritative(complete);
      mediaDraft.reset();
      setActionError(null);
    } catch (reason) {
      if (requestId !== loadRequestRef.current) return;
      setLoadError(asApiError(reason));
    }
  }, [id, applyAuthoritative, mediaDraft.reset]);

  useEffect(() => { void load(); }, [load]);

  const availableProducts = useMemo(
    () => componentProducts.filter((candidate) => candidate.id !== product?.id && candidate.type === "single" && candidate.active),
    [componentProducts, product?.id],
  );

  useEffect(() => {
    if (!product) return;
    void editorApi.adminProducts().then((page) => setComponentProducts(page.items)).catch(() => undefined);
  }, [product?.id]);

  function clearMessages() {
    setActionError(null);
    setSuccessMessage(null);
  }

  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!product || busy !== null || conflictNeedsReload) return;
    const amountMinor = parseRublesToMinor(priceRubles);
    if (amountMinor === null || BigInt(amountMinor) <= 0n) return setActionError("Введите действительную цену в рублях: например, 150 или 150,50.");
    const originalMinor = originalPriceRubles.trim() ? parseRublesToMinor(originalPriceRubles) : null;
    if (originalPriceRubles.trim() && (originalMinor === null || BigInt(originalMinor) <= 0n)) return setActionError("Введите корректную цену до скидки или оставьте поле пустым.");
    if (originalMinor !== null && BigInt(originalMinor) < BigInt(amountMinor)) return setActionError("Цена до скидки должна быть не меньше действительной цены.");
    clearMessages();
    setBusy("save");
    ++loadRequestRef.current;
    try {
      const commands: ProductSaveCommand<AdminEditorProduct>[] = [];
      const patch = { title: title.trim(), description, active, attributes: attributesObject(attributes), related_product_ids: relatedProductIds };
      const previous = { title: product.title, description: product.description, active: product.active, attributes: product.attributes, related_product_ids: product.related_product_ids ?? [] };
      if (JSON.stringify(patch) !== JSON.stringify(previous)) commands.push({ run: (current) => editorApi.updateAdminProduct(current.id, patch, current.version) });
      if (amountMinor !== minorPrice(product) || (originalMinor ?? "") !== originalMinorPrice(product)) {
        const command = { price: { amount_minor: amountMinor, currency: "RUB" }, original_price: originalMinor === null ? null : { amount_minor: originalMinor, currency: "RUB" } } as Parameters<typeof editorApi.setAdminSitePrice>[1];
        commands.push({ run: (current) => editorApi.setAdminSitePrice(current.id, command, current.version) });
      }
      if (product.type === "bundle" && JSON.stringify(components) !== JSON.stringify(bundleRows(product.bundle))) {
        const command = { components: components.map((component) => ({ product_id: component.product_id, quantity: Number(component.quantity) })) };
        commands.push({ run: async (current) => { await editorApi.replaceAdminBundle(current.id, command, current.version); } });
      }
      const complete = await saveProductDraft({
        product, commands, additions: mediaDraft.additions, removals: mediaDraft.removals,
        api: {
          read: (productId) => editorApi.adminProduct(productId),
          remove: (productId, mediaId, version) => editorApi.deleteAdminMedia(productId, mediaId, version),
          upload: (productId, addition, position, version) => {
            setUploadKind(addition.type);
            setUploadProgress(0);
            return editorApi.uploadAdminMedia(productId, addition.file, { alt_text: "", position }, version, addition.filename, setUploadProgress);
          },
        },
        onProduct: setProduct,
        onAdditionSaved: mediaDraft.discard,
        onRemovalSaved: mediaDraft.removalSaved,
      });
      applyAuthoritative(complete);
      setSuccessMessage("Все изменения сохранены.");
    } catch (reason) {
      const error = asApiError(reason);
      if (isProductVersionConflict(error)) {
        setConflictNeedsReload(true);
        const recovered = await recoverProductConflict(product.id, editorApi.adminProduct, applyAuthoritative, mediaDraft.reset);
        setActionError(recovered
          ? "Данные изменились в другой вкладке. Загружена актуальная карточка, несохранённый черновик сброшен. Проверьте данные и заново внесите нужные изменения перед сохранением."
          : "Данные изменились в другой вкладке. Не удалось загрузить актуальную карточку; черновик и локальные файлы сохранены, сохранение заблокировано. Загрузите товар заново для проверки данных и повторного внесения изменений. Черновик будет сброшен только после успешной загрузки.");
        return;
      }
      // Keep the last acknowledged version and the local draft. Reading only a
      // newer version here would allow stale fields to overwrite concurrent edits.
      setConflictNeedsReload(true);
      setActionError("Сохранение не завершено. Часть изменений могла сохраниться. Черновик и локальные файлы сохранены; повторное сохранение заблокировано. Загрузите актуальную карточку, проверьте данные и повторно внесите изменения. Черновик будет сброшен только после успешной загрузки. " + errorText(error, "сохранить товар"));
    } finally {
      setBusy(null);
      setUploadProgress(null);
      setUploadKind(null);
    }
  }

  if (loadError) {
    return <Card><Notice tone="warning">{loadError.status === 404 ? "Товар не найден." : "Не удалось загрузить товар. Повторите попытку позже."}</Notice><Button variant="secondary" onClick={() => void load()}>Повторить</Button></Card>;
  }
  if (!product) return <Loading label="Загружаем товар…" />;

  return <>
    <div className="admin-editor-heading"><div><p className="muted">Catalog · protected scope catalog.write</p><h1>Редактирование товара</h1><p className="muted">{product.sku} · версия {product.version}</p></div><Button variant="secondary" onClick={() => router.push("/products")}>← К товарам</Button></div>
    {actionError && <Notice tone="warning"><span role="alert">{actionError}</span> {(conflictNeedsReload || actionError.includes("изменились")) && <button type="button" className="link-button" onClick={() => void load()}>Загрузить заново</button>}</Notice>}
    {successMessage && <Notice tone="success">{successMessage}</Notice>}
    <form onSubmit={(event) => void saveProduct(event)}><fieldset className="editor-fieldset" disabled={busy !== null || conflictNeedsReload}>
    <Card><h2>Основные данные</h2><div className="admin-editor-form"><label>Название<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={300} required /></label><label>SKU<input value={product.sku} readOnly aria-readonly="true" /><span className="muted">SKU нельзя изменить после создания товара.</span></label><label>Описание<textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={10000} rows={6} /></label><label className="checkbox-label"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} /> Опубликован на сайте</label></div></Card>
    <Card><div className="editor-section-heading"><div><h2>Характеристики</h2><p className="muted">Пары «название — значение» отображаются в карточке товара.</p></div><Button type="button" variant="secondary" onClick={() => { setAttributes((current) => [...current, { id: nextAttributeId, name: "", value: "" }]); setNextAttributeId((current) => current + 1); }}>Добавить характеристику</Button></div>{attributes.length ? <div className="attribute-editor-list">{attributes.map((row, index) => <div className="attribute-editor-row" key={row.id}><label>Название характеристики<input value={row.name} onChange={(event) => setAttributes((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, name: event.target.value } : item))} /></label><label>Значение<input value={row.value} onChange={(event) => setAttributes((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, value: event.target.value } : item))} /></label><button type="button" className="button button-secondary" onClick={() => setAttributes((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Удалить</button></div>)}</div> : <p className="muted">Характеристики ещё не добавлены.</p>}</Card>
    <Card><h2>Цена сайта</h2><p className="muted">Введите сумму в рублях. Цена до скидки будет показана у покупателя зачёркнутой.</p><div className="admin-editor-form"><label>Цена на сайте, ₽<input inputMode="decimal" value={priceRubles} onChange={(event) => setPriceRubles(event.target.value)} placeholder="Например, 150 или 150,50" required /></label><label>Цена до скидки, ₽ <span className="muted">необязательно</span><input inputMode="decimal" value={originalPriceRubles} onChange={(event) => setOriginalPriceRubles(event.target.value)} placeholder="Например, 200" /></label><p className="muted">Текущее отображение: {formatMoney(product.price)}{product.original_price ? ` · до скидки ${formatMoney(product.original_price)}` : ""}</p></div></Card>
    <Card><div className="editor-section-heading"><div><h2>Варианты товара</h2><p className="muted">Выберите карточки одной группы, например варианты цвета. Покупатель сможет переключаться между ними в карточке товара.</p></div></div>{componentProducts.length ? <div className="admin-editor-form"><div className="related-product-list">{componentProducts.filter((candidate) => candidate.id !== product.id).map((candidate) => <label className="related-product-option" key={candidate.id}><input type="checkbox" checked={relatedProductIds.includes(candidate.id)} onChange={() => setRelatedProductIds((current) => current.includes(candidate.id) ? current.filter((id) => id !== candidate.id) : [...current, candidate.id])} /><span><strong>{candidate.title}</strong><small>{candidate.sku}</small></span></label>)}</div></div> : <p className="muted">Других товаров пока нет.</p>}</Card>
    {product.type === "bundle" && <Card><h2>Состав комплекта</h2><p className="muted">Компоненты проверяются сервером. В комплект можно добавить активные товары типа single.</p><div className="admin-editor-form"><div className="bundle-editor-list">{components.map((component, index) => <div className="bundle-editor-row" key={`${component.product_id}-${index}`}><label>Товар<select value={component.product_id} onChange={(event) => setComponents((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, product_id: event.target.value } : row))} required><option value="">Выберите товар</option>{availableProducts.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.title} · {candidate.sku}</option>)}</select></label><label>Количество<input type="number" min="1" max="2147483647" value={component.quantity} onChange={(event) => setComponents((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, quantity: event.target.value } : row))} required /></label><button type="button" className="button button-secondary bundle-remove" onClick={() => setComponents((current) => current.filter((_, rowIndex) => rowIndex !== index))}>Удалить</button></div>)}</div><div className="editor-actions"><Button type="button" variant="secondary" onClick={() => setComponents((current) => [...current, { product_id: "", quantity: "1" }])}>Добавить компонент</Button></div></div></Card>}
    <ProductMedia title={title} media={product.media} draft={mediaDraft} busy={busy !== null || conflictNeedsReload} uploadProgress={uploadProgress} uploadKind={uploadKind} />
    <div className="editor-submit-row"><Button type="submit" disabled={busy !== null || conflictNeedsReload}>{busy !== null ? "Сохраняем…" : "Сохранить"}</Button></div>
    </fieldset></form>
  </>;
}
