import type { Metadata } from "next";
import CheckoutClient from "./checkout-client";

export const metadata: Metadata = { title: "Заявка", robots: { index: false, follow: false }, alternates: { canonical: "/checkout" } };
export default function CheckoutPage() { return <CheckoutClient />; }
