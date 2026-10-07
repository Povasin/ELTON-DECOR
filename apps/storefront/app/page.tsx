import Link from "next/link";
import HomeProducts from "./home-products";

export default function HomePage() {
  return <>
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-copy"><p className="eyebrow">Elton Decor · warm editorial objects</p><h1 id="hero-title">Пространство с характером.</h1><p>Вазы, цвет и свет, которые делают комнату личной. Выбирайте предметы для дома в спокойном темпе.</p><Link className="button button-primary" href="/catalog">Смотреть каталог</Link></div>
      <div className="hero-art" aria-label="Декоративная композиция" role="img" />
    </section>
    <section aria-labelledby="home-products"><div className="section-head"><h2 id="home-products">Предметы Elton Decor</h2><Link href="/catalog" className="muted">Весь каталог →</Link></div><HomeProducts /></section>
  </>;
}
