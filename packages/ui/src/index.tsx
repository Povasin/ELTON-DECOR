import type { ButtonHTMLAttributes, ReactNode } from "react";

export function BrandMark() {
  return <span className="brand-mark" aria-label="Elton Decor">ELTON <i>DECOR</i></span>;
}

export function Button({ variant = "primary", children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "quiet" }) {
  return <button className={`button button-${variant}`} {...props}>{children}</button>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warning" | "success" }) {
  return <div className={`notice notice-${tone}`} role={tone === "warning" ? "alert" : "status"}>{children}</div>;
}

export function PageIntro({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return <div className="page-intro">{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{children && <p className="lede">{children}</p>}</div>;
}

export function Loading({ label = "Загружаем данные" }: { label?: string }) {
  return <p className="loading" role="status"><span className="loading-dot" aria-hidden="true" />{label}</p>;
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty-state"><h2>{title}</h2>{children && <p>{children}</p>}</div>;
}

export function DeliveryNote() {
  return <p className="muted">Доставка пока не подключена. Сумма доставки и итог появятся после подключения провайдера.</p>;
}

export function AvailabilityNote() {
  return <p className="muted">Наличие уточняется перед подключением реального заказа.</p>;
}
