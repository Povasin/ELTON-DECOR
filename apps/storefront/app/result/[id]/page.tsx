import type { Metadata } from "next";
import ResultClient from "./result-client";

export const metadata: Metadata = { title: "Результат заявки", robots: { index: false, follow: false }, alternates: { canonical: "/result" } };
export default function ResultPage() { return <ResultClient />; }
