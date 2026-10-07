"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Card, Notice } from "@elton/ui";
import { hasAtMostOneVideo, sortAdminMedia, stageAdminMedia, type AdminMediaLike } from "../lib/media";
import type { MediaAddition } from "../lib/product-save";

export type PendingMedia = MediaAddition & { previewUrl: string };

export function useMediaDraft() {
  const [additions, setAdditions] = useState<PendingMedia[]>([]);
  const [removals, setRemovals] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const urls = useRef(new Map<string, { url: string; type: "image" | "video" }>());
  useEffect(() => () => { for (const { url } of urls.current.values()) URL.revokeObjectURL(url); }, []);
  function add(files: File[], type: "image" | "video", media: AdminMediaLike[] = []) {
    if (!files.length) return;
    if (type === "video" && !hasAtMostOneVideo(media, removals, [{ type: "video" }])) {
      setError("В карточке разрешено одно видео. Сначала отметьте сохранённое видео для удаления, затем выберите новый файл.");
      return;
    }
    setError(null);
    if (type === "video") {
      for (const [id, entry] of urls.current) {
        if (entry.type !== "video") continue;
        URL.revokeObjectURL(entry.url);
        urls.current.delete(id);
      }
    }
    const selected = (type === "video" ? files.slice(-1) : files).map((file) => {
      const id = crypto.randomUUID();
      const previewUrl = URL.createObjectURL(file);
      urls.current.set(id, { url: previewUrl, type });
      return { id, file, filename: file.name, type, previewUrl };
    });
    setAdditions((current) => stageAdminMedia(current, selected));
  }
  function discard(id: string) {
    setError(null);
    const entry = urls.current.get(id);
    if (entry) URL.revokeObjectURL(entry.url);
    urls.current.delete(id);
    setAdditions((current) => current.filter((item) => item.id !== id));
  }
  function toggleRemoval(id: string, media: AdminMediaLike[] = []) {
    const next = removals.includes(id) ? removals.filter((item) => item !== id) : [...removals, id];
    if (!hasAtMostOneVideo(media, next, additions)) {
      setError("Нельзя восстановить сохранённое видео, пока выбран новый файл. Сначала уберите новый файл.");
      return;
    }
    setError(null);
    setRemovals(next);
  }
  function removalSaved(id: string) { setRemovals((current) => current.filter((item) => item !== id)); }
  const reset = useCallback(() => {
    for (const { url } of urls.current.values()) URL.revokeObjectURL(url);
    urls.current.clear();
    setAdditions([]);
    setRemovals([]);
    setError(null);
  }, []);
  return { additions, removals, error, add, discard, toggleRemoval, removalSaved, reset };
}

export function ProductMedia({ title, media = [], draft, busy, uploadProgress, uploadKind }: {
  title: string;
  media?: AdminMediaLike[];
  draft: ReturnType<typeof useMediaDraft>;
  busy: boolean;
  uploadProgress: number | null;
  uploadKind: "image" | "video" | null;
}) {
  return <>{(["image", "video"] as const).map((kind) => {
    const isImage = kind === "image";
    const saved = sortAdminMedia(media).filter((item) => item.type === kind);
    const pending = draft.additions.filter((item) => item.type === kind);
    const firstImageId = sortAdminMedia(media).find((item) => item.type === "image" && !draft.removals.includes(item.id))?.id
      ?? draft.additions.find((item) => item.type === "image")?.id;
    return <Card key={kind}>
      <div className="editor-section-heading"><div><h2>{isImage ? "Изображения" : "Видео"}</h2><p className="muted">{isImage ? "Первое изображение станет главной фотографией товара. Добавляйте изображения в нужном порядке." : "Видео показывается после всех изображений. MP4 H.264/HEVC до 60 секунд."}</p><p className="muted">Добавление и удаление вступят в силу после нажатия «Сохранить».</p></div>
        <label className={`button${busy ? " button-disabled" : ""}`}>{isImage ? "Добавить изображения" : "Добавить видео"}<input className="visually-hidden" type="file" accept={isImage ? "image/jpeg,image/png,image/webp" : "video/mp4,.mp4"} multiple={isImage} disabled={busy} onChange={(event) => { const files = Array.from(event.target.files ?? []); event.target.value = ""; draft.add(files, kind, media); }} /></label>
      </div>
      {!isImage && draft.error && <Notice tone="warning"><span role="alert">{draft.error}</span></Notice>}
      {uploadKind === kind && uploadProgress !== null && <div className="upload-progress" aria-label={isImage ? "Прогресс загрузки изображения" : "Прогресс загрузки видео"}><div className="upload-progress-label"><span role="status" aria-live="polite">{uploadProgress === 100 ? "Проверяем файл на сервере…" : "Загружаем файл…"}</span><strong>{uploadProgress}%</strong></div><progress max={100} value={uploadProgress}>Загрузка: {uploadProgress}%</progress></div>}
      {saved.length || pending.length ? <div className="media-grid">
        {saved.map((item) => <div className={`media-item${draft.removals.includes(item.id) ? " media-pending-removal" : ""}`} key={item.id}>{isImage ? <img src={item.url} alt={item.alt_text || title} /> : <video controls preload="metadata" playsInline src={item.url} aria-label={`Видео товара ${title}`} />}<div className="media-item-footer"><span>{draft.removals.includes(item.id) ? "Будет удалено" : item.id === firstImageId ? "Главное фото" : isImage ? "Изображение" : "Видео"}</span><button type="button" className="link-button" disabled={busy} onClick={() => draft.toggleRemoval(item.id, media)}>{draft.removals.includes(item.id) ? "Отменить" : "Удалить"}</button></div></div>)}
        {pending.map((item) => <div className="media-item media-pending-upload" key={item.id}>{isImage ? <img src={item.previewUrl} alt={item.filename} /> : <video controls preload="metadata" playsInline src={item.previewUrl} aria-label={`Выбранное видео ${item.filename}`} />}<div className="media-item-footer"><span>{item.id === firstImageId ? "Главное фото · не сохранено" : "Ожидает сохранения"}<small>{item.filename}</small></span><button type="button" className="link-button" disabled={busy} onClick={() => draft.discard(item.id)}>Убрать</button></div></div>)}
      </div> : <p className="muted">{isImage ? "Изображения ещё не добавлены." : "Видео ещё не добавлено."}</p>}
    </Card>;
  })}</>;
}
