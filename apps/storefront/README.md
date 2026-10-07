# Storefront

Планируемое приложение Next.js / TypeScript: главная, каталог/PDP, корзина, guest checkout, SMS вход/ЛК, SEO и клиентские события. Сейчас содержит только описание; runtime ещё не создан.

Владелец: Frontend. Вход: [PRODUCT](../../docs/PRODUCT.md), [BUSINESS_RULES](../../docs/BUSINESS_RULES.md), [API](../../docs/API.md), [профиль](../../docs/agents/FRONTEND.md).

Только Elton API. Никаких Ozon credentials/прямых calls или authoritative денег/статусов в браузере. Shared UI — `packages/ui`. Public catalog можно кэшировать; cart/account/checkout нельзя помещать в общий CDN cache. Конкретные caching headers проектируются в ARCHITECTURE/API.

Для локального запуска задайте серверные `ELTON_SITE_URL` и `ELTON_API_URL` (пример — в корневом `.env.example`). `ELTON_SITE_URL` используется для canonical metadata, Product/Breadcrumb JSON-LD, sitemap и robots; при отсутствии или некорректном значении используется `http://localhost:3000`. `ELTON_API_URL` никогда не принимается из browser request.
