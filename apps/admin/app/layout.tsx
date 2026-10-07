import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@elton/ui";
import { AdminControls } from "../components/admin-controls";
import "./globals.css";

export const metadata: Metadata = { title: { default: "Elton Decor Admin", template: "%s — Elton Decor Admin" }, robots: { index: false, follow: false } };

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="ru"><body><div className="admin-shell"><header className="admin-header"><Link href="/" aria-label="Elton Decor admin"><BrandMark /></Link><nav className="admin-nav" aria-label="Админ-навигация"><Link href="/products">Товары</Link><Link href="/drafts">Заявки</Link><AdminControls /></nav></header><main className="admin-content">{children}</main></div></body></html>; }
