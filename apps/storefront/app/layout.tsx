import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@elton/ui";
import { siteUrl } from "../lib/site";
import AnalyticsPageView from "./analytics-page-view";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Elton Decor — предметы с характером", template: "%s — Elton Decor" },
  description: "Тёплый интерьерный декор Elton Decor.",
  metadataBase: siteUrl(),
  alternates: { canonical: "/" },
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ru"><body><AnalyticsPageView /><header className="site-header"><Link href="/" aria-label="Elton Decor, на главную"><BrandMark /></Link><nav className="nav" aria-label="Основная навигация"><Link href="/catalog">Каталог</Link><Link href="/about">О бренде</Link><Link className="cart-link" href="/cart">Корзина</Link></nav></header><main className="main">{children}</main><footer className="footer">Elton Decor · локальная заявка без оплаты и доставки на этапе демонстрации</footer></body></html>;
}
