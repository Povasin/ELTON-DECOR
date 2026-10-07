import type { Metadata } from "next";
import CartClient from "./cart-client";

export const metadata: Metadata = { title: "Корзина", robots: { index: false, follow: false }, alternates: { canonical: "/cart" } };
export default function CartPage() { return <CartClient />; }
