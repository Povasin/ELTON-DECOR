"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, formatMoney, type ProductDetail, type ProductSummary } from "@elton/api-client";
import { trackEvent } from "@elton/analytics";
import { AvailabilityNote, Button, Card, DeliveryNote, Loading, Notice } from "@elton/ui";
import { cartQuantity, nextQuantityChange } from "../../../lib/product-quantity";
import { getOriginalPrice, getProductAttributes, getVariantProducts, isDiscounted, type ProductWithCatalogFields } from "../../../lib/product-fields";
import ProductGallery from "./product-gallery";

export default function ProductClient({ initialProduct = null }: { initialProduct?: ProductDetail | null }) {
  const { slug } = useParams<{ slug: string }>();
  const [product, setProduct] = useState<ProductDetail | null>(initialProduct);
  const [productError, setProductError] = useState<ApiError | null>(null);
  const [cartError, setCartError] = useState<ApiError | null>(null);
  const [updatingCart, setUpdatingCart] = useState(false);
  const [added, setAdded] = useState(false);
  const [quantity, setQuantity] = useState(0);
  const [cartVersion, setCartVersion] = useState<number | null>(null);
  const [relatedCandidates, setRelatedCandidates] = useState<ProductSummary[]>([]);

  useEffect(() => { if (!slug || initialProduct) return; void api.product(slug).then(setProduct).catch((reason: unknown) => setProductError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true }))); }, [initialProduct, slug]);
  useEffect(() => {
    if (!product?.related_product_ids?.length) return;
    void api.products({ limit: 100 }).then((page) => setRelatedCandidates(page.items)).catch(() => setRelatedCandidates([]));
  }, [product]);
  useEffect(() => { if (product) trackEvent({ name: "view_product", product_id: product.id }); }, [product]);

  if (productError) return <Notice tone="warning">Товар не найден или временно недоступен. Код: {productError.problem.code ?? "NOT_FOUND"}.</Notice>;
  if (!product) return <Loading />;
  const productId = product.id;

  async function addToCart() {
    setUpdatingCart(true);
    setCartError(null);
    try {
      const cart = await api.cart();
      const nextCart = await api.setQuantity(productId, cartQuantity(cart.items, productId) + 1, cart.version);
      setQuantity(cartQuantity(nextCart.items, productId));
      setCartVersion(nextCart.version);
      setAdded(true);
      trackEvent({ name: "add_to_cart", product_id: productId, quantity: 1 });
    } catch (reason) { setCartError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true })); } finally { setUpdatingCart(false); }
  }

  async function changeQuantity(direction: 1 | -1) {
    if (!added || cartVersion === null || quantity < 1) return;
    setUpdatingCart(true);
    setCartError(null);
    try {
      const change = nextQuantityChange(quantity, direction);
      const nextCart = change.kind === "remove"
        ? await api.removeLine(productId, cartVersion)
        : await api.setQuantity(productId, change.quantity, cartVersion);
      const nextQuantity = cartQuantity(nextCart.items, productId);
      setQuantity(nextQuantity);
      setCartVersion(nextCart.version);
      setAdded(nextQuantity > 0);
      trackEvent({ name: change.kind === "remove" ? "remove_from_cart" : "add_to_cart", product_id: productId, quantity: change.kind === "remove" ? undefined : 1 });
    } catch (reason) { setCartError(reason instanceof ApiError ? reason : new ApiError(503, { retryable: true })); } finally { setUpdatingCart(false); }
  }

  const media = product.media ?? [];
  const catalogProduct = product as ProductWithCatalogFields;
  const originalPrice = getOriginalPrice(catalogProduct);
  const discounted = isDiscounted(catalogProduct);
  const attributes = getProductAttributes(product);
  const variants = getVariantProducts(catalogProduct, relatedCandidates);
  return <><nav className="muted" aria-label="Хлебные крошки"><Link href="/catalog">Каталог</Link> / {product.title}</nav><div className="detail-layout"><ProductGallery title={product.title} media={media} /><div className="detail-content"><p className="eyebrow">{product.type === "bundle" ? "Комплект" : "Elton Decor"}</p><h1>{product.title}</h1><div className="detail-price">{discounted && originalPrice && <del className="price-original">{formatMoney(originalPrice)}</del>}<p className="price">{formatMoney(product.price)}</p></div><p>{product.description || "Предмет для интерьера с характером и спокойной формой."}</p><AvailabilityNote /><DeliveryNote /><div className="card"><div className="product-cart-action">{added ? <div className="product-quantity" role="group" aria-label="Количество товара в корзине"><button type="button" className="product-quantity-button" onClick={() => void changeQuantity(-1)} disabled={updatingCart} aria-label="Уменьшить количество">−</button><output aria-live="polite">{quantity}</output><button type="button" className="product-quantity-button" onClick={() => void changeQuantity(1)} disabled={updatingCart} aria-label="Увеличить количество">+</button></div> : <Button onClick={addToCart} disabled={updatingCart}>{updatingCart ? "Добавляем…" : "Добавить в корзину"}</Button>}{added && <Link className="button button-secondary" href="/cart">Корзина →</Link>}</div>{cartError && <Notice tone="warning">Не удалось обновить корзину. Код: {cartError.problem.code ?? "STORAGE_TEMPORARILY_UNAVAILABLE"}.</Notice>}{added && <Notice tone="success">Товар в корзине. Можно изменить количество или перейти в корзину.</Notice>}</div></div></div><Card><h2>Характеристики</h2>{attributes.length ? <dl className="attribute-list">{attributes.map((attribute) => <div key={`${attribute.name}-${attribute.value}`}><dt className="muted">{attribute.name}</dt><dd>{attribute.value}</dd></div>)}</dl> : <p className="muted">Характеристики появятся после заполнения карточки.</p>}</Card>{variants.length > 0 && <section className="card related-products" aria-labelledby="variant-products-title"><div className="section-head"><div><p className="eyebrow">Варианты</p><h2 id="variant-products-title">Выберите цвет или вариант</h2></div></div><div className="related-grid">{variants.map((variant) => { const variantWithPrice = variant as ProductSummary & { original_price?: ProductDetail["price"] | null }; const variantOriginalPrice = getOriginalPrice(variantWithPrice); return <Link key={variant.id} href={`/products/${variant.slug}`} className="related-card"><div className="related-card-image">{variant.thumbnail?.url ? <img src={variant.thumbnail.url} alt={variant.title} loading="lazy" /> : <span aria-hidden="true" />}</div><div className="related-card-copy">{variantOriginalPrice && isDiscounted(variantWithPrice) && <del className="price-original">{formatMoney(variantOriginalPrice)}</del>}<strong>{variant.title}</strong><span>{formatMoney(variant.price)}</span></div></Link>; })}</div></section>}</>;
}
