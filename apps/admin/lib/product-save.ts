import { appendAdminMedia, hasAtMostOneVideo, removeAdminMedia, sortAdminMedia, type AdminMediaLike } from "./media";

export type MediaAddition = { id: string; type: "image" | "video"; file: Blob; filename: string };
export type SavableProduct = { id: string; version: number; media?: AdminMediaLike[] };
export type ProductSaveCommand<P> = { run: (current: P) => Promise<Partial<P> | void> };

export function isProductVersionConflict(error: { status: number; problem: { code?: string; detail?: string } }): boolean {
  if (error.problem.code === "CAPABILITY_DISABLED" || error.problem.detail === "CAPABILITY_DISABLED") return false;
  return error.status === 409 || error.problem.code === "VERSION_CONFLICT";
}

/** A failed read keeps local files intact and saving blocked. */
export async function recoverProductConflict<P>(
  productId: string,
  read: (id: string) => Promise<P>,
  applyAuthoritative: (product: P) => void,
  clearDraft: () => void,
): Promise<boolean> {
  try {
    const product = await read(productId);
    applyAuthoritative(product);
    clearDraft();
    return true;
  } catch {
    return false;
  }
}

/** Sequential commands share the product version; only a detail read replaces gallery state. */
export async function saveProductDraft<P extends SavableProduct>(options: {
  product: P;
  commands: ProductSaveCommand<P>[];
  additions: MediaAddition[];
  removals: string[];
  api: {
    read: (id: string) => Promise<P>;
    remove: (id: string, mediaId: string, version: number) => Promise<unknown>;
    upload: (id: string, addition: MediaAddition, position: number, version: number) => Promise<AdminMediaLike>;
  };
  onProduct?: (product: P) => void;
  onAdditionSaved?: (id: string) => void;
  onRemovalSaved?: (id: string) => void;
}): Promise<P> {
  if (!hasAtMostOneVideo(options.product.media ?? [], options.removals, options.additions)) {
    throw new Error("В карточке разрешено одно видео. Удалите прежнее видео перед добавлением нового.");
  }
  let current = options.product;
  const show = (product: P) => { current = product; options.onProduct?.(product); };
  const refresh = async () => show(await options.api.read(current.id));
  for (const command of options.commands) {
    const updated = await command.run(current);
    // Mutation DTOs can omit gallery details. Never replace it with a partial
    // response; the final GET is the authoritative complete snapshot.
    if (updated) show({ ...current, ...updated, media: current.media });
    else await refresh();
  }
  for (const mediaId of options.removals) {
    await options.api.remove(current.id, mediaId, current.version);
    show({ ...current, media: removeAdminMedia(current.media, mediaId) });
    options.onRemovalSaved?.(mediaId);
    await refresh();
  }
  // Stable ordering also keeps a staged video behind every staged image.
  const additions = [...options.additions].sort((a, b) => Number(a.type === "video") - Number(b.type === "video"));
  for (const addition of additions) {
    if (addition.type === "video" && !hasAtMostOneVideo(current.media ?? [], [], [addition])) {
      throw new Error("В карточке разрешено одно видео. Загрузите актуальную карточку перед заменой видео.");
    }
    const media = current.media ?? [];
    const sameType = media.filter((item) => item.type === addition.type);
    const position = addition.type === "image"
      ? Math.max(-1, ...sameType.map((item) => item.position)) + 1
      : Math.max(-1, ...media.map((item) => item.position)) + 1;
    const uploaded = await options.api.upload(current.id, addition, position, current.version);
    show({ ...current, media: appendAdminMedia(current.media, uploaded) });
    // Remove the local draft before GET: a failed refresh must not re-upload
    // an already acknowledged file on the next explicit Save.
    options.onAdditionSaved?.(addition.id);
    await refresh();
  }
  await refresh();
  return { ...current, media: sortAdminMedia(current.media ?? []) };
}
