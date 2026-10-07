import type { Metadata } from "next";
import { PageIntro, Card, Notice } from "@elton/ui";

export const metadata: Metadata = { title: "О бренде", alternates: { canonical: "/about" } };

export default function AboutPage() {
  return <><PageIntro eyebrow="О бренде" title="Дом начинается с деталей." >Elton Decor собирает интерьерные предметы для спокойных, живых пространств.</PageIntro><Card><h2>Демонстрационный этап</h2><p>Сейчас можно изучать каталог, складывать товары в гостевую корзину и отправить локальную заявку. Она не является оплатой или подтверждённым заказом.</p><Notice>Оплата и доставка пока не подключены. Мы покажем их стоимость только после проверки внешнего контракта.</Notice></Card></>;
}
