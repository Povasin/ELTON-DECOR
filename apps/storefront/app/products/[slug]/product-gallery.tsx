"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { nextGalleryIndex, previousGalleryIndex, sortGalleryMedia, type GalleryMedia } from "../../../lib/gallery";

type ProductGalleryProps = {
  title: string;
  media: GalleryMedia[];
};

function MediaFrame({ item, title }: { item: GalleryMedia; title: string }) {
  const label = item.alt_text || `${item.type === "video" ? "Видео" : "Изображение"} товара ${title}`;
  if (item.type === "video") {
    return <video className="gallery-media gallery-media-video" controls preload="metadata" playsInline src={item.url} aria-label={label} />;
  }
  return <GalleryImage className="gallery-media" src={item.url} alt={label} />;
}

function GalleryImage({ className, src, alt }: { className: string; src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <div className={className + " gallery-media-fallback"} role="img" aria-label={alt + ": изображение недоступно"}>Изображение недоступно</div>;
  }
  return <img className={className} src={src} alt={alt} draggable={false} onError={() => setFailed(true)} />;
}

function ThumbnailImage({ item, title, loading }: { item: GalleryMedia; title: string; loading: "eager" | "lazy" }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <span className="gallery-thumbnail-fallback" role="img" aria-label={"Изображение товара " + title + " недоступно"}>×</span>;
  return <img src={item.url} alt="" loading={loading} onError={() => setFailed(true)} />;
}

export default function ProductGallery({ title, media }: ProductGalleryProps) {
  const sortedMedia = useMemo(() => sortGalleryMedia(media), [media]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [viewerOpen, setViewerOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const thumbnailRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const activeItem = sortedMedia[activeIndex] ?? sortedMedia[0];

  useEffect(() => {
    setActiveIndex((current) => sortedMedia.length ? Math.min(current, sortedMedia.length - 1) : 0);
  }, [sortedMedia.length]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (viewerOpen && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    if (!viewerOpen && dialog.open) dialog.close();
  }, [viewerOpen]);

  function focusActiveThumbnail() {
    if (activeItem) thumbnailRefs.current[activeItem.id]?.focus();
  }

  function closeViewer() {
    const dialog = dialogRef.current;
    if (dialog?.open) dialog.close();
    else dialog?.removeAttribute("open");
    setViewerOpen(false);
    window.setTimeout(focusActiveThumbnail, 0);
  }

  function openViewer() {
    if (!activeItem) return;
    setViewerOpen(true);
  }

  function selectMedia(index: number) {
    setActiveIndex(index);
  }

  function showPrevious() {
    setActiveIndex((current) => previousGalleryIndex(current, sortedMedia.length));
  }

  function showNext() {
    setActiveIndex((current) => nextGalleryIndex(current, sortedMedia.length));
  }

  function handleViewerKeyDown(event: React.KeyboardEvent<HTMLDialogElement>) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      showPrevious();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      showNext();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeViewer();
    }
  }

  if (!activeItem) {
    return <div className="detail-art" aria-label={`Медиа товара ${title}`}><div className="detail-art-placeholder" role="img" aria-label={`Иллюстрация товара ${title}`} /></div>;
  }

  return <div className="detail-art gallery-shell" aria-label={`Галерея товара ${title}`}>
    <div className={`gallery-stage${activeItem.type === "video" ? " gallery-stage-video" : ""}`}>
      <MediaFrame key={"stage-" + activeItem.id} item={activeItem} title={title} />
      <div className="gallery-stage-actions">
        {sortedMedia.length > 1 && <>
          <button type="button" className="gallery-control" onClick={showPrevious} aria-label="Предыдущее медиа">‹</button>
          <button type="button" className="gallery-control" onClick={showNext} aria-label="Следующее медиа">›</button>
        </>}
        <button type="button" className="gallery-expand" onClick={openViewer} aria-label="Открыть медиа на весь экран">⤢ <span>На весь экран</span></button>
      </div>
      <span className="gallery-counter" aria-live="polite">{activeIndex + 1} / {sortedMedia.length}</span>
    </div>
    <div className="gallery-thumbnails" role="group" aria-label="Миниатюры товара">
      {sortedMedia.map((item, index) => <button
        type="button"
        className={`gallery-thumbnail${index === activeIndex ? " is-active" : ""}`}
        key={item.id}
        ref={(node) => { thumbnailRefs.current[item.id] = node; }}
        aria-label={`${item.type === "video" ? "Видео" : "Изображение"} ${index + 1}: ${item.alt_text || title}`}
        aria-pressed={index === activeIndex}
        onClick={() => selectMedia(index)}
      >
        {item.type === "image" ? <ThumbnailImage item={item} title={title} loading={index === 0 ? "eager" : "lazy"} /> : <span className="gallery-thumbnail-video" aria-hidden="true">▶</span>}
        <span className="sr-only">{item.type === "video" ? "Видео" : "Фото"}</span>
      </button>)}
    </div>
    <dialog ref={dialogRef} className="gallery-dialog" aria-label={`Полноэкранная галерея товара ${title}`} onCancel={(event) => { event.preventDefault(); closeViewer(); }} onClose={() => { setViewerOpen(false); window.setTimeout(focusActiveThumbnail, 0); }} onKeyDown={handleViewerKeyDown}>
      <div className={`gallery-dialog-inner${activeItem.type === "video" ? " gallery-stage-video" : ""}`}>
        <MediaFrame key={"dialog-" + activeItem.id} item={activeItem} title={title} />
        <button type="button" className="gallery-dialog-close" onClick={closeViewer} aria-label="Закрыть полноэкранный просмотр">×</button>
        {sortedMedia.length > 1 && <div className="gallery-dialog-controls"><button type="button" className="gallery-control" onClick={showPrevious} aria-label="Предыдущее медиа">‹</button><button type="button" className="gallery-control" onClick={showNext} aria-label="Следующее медиа">›</button></div>}
        <span className="gallery-counter" aria-live="polite">{activeIndex + 1} / {sortedMedia.length}</span>
      </div>
    </dialog>
  </div>;
}
