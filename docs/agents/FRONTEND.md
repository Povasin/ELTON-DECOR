# Рабочий профиль: Frontend + Admin UI + SEO

## Мандат

Next.js storefront, каталог, PDP, корзина, checkout UI, ЛК, admin UI, общие компоненты и SEO. Не обращаться к Ozon напрямую; не вычислять authoritative цены, скидки, возвраты или provider статусы в браузере.

## Вход

Обязательно: `AGENTS.md`, PRODUCT, MVP_SCOPE, BUSINESS_RULES, API, ARCHITECTURE, DECISIONS, QA. Для админки — DATABASE/OZON_INTEGRATION на уровне ownership данных. Дизайн — утверждённый Figma, прототипы MagicPath только как исследование.

## Область записи

`apps/storefront/`, `apps/admin/`, `packages/ui/`; клиентская инструментализация событий по контракту `packages/analytics`. Общую schema события менять через Architect/Backend review. Не менять backend, миграции или Ozon adapter.

## Правила

- Первый этап поддерживает гостевую корзину и оформление локальной заявки без оплаты/доставки. SMS/ЛК — следующий коммерческий этап по MVP_SCOPE; OAuth/избранное не появляются самостоятельно.
- Все операции через Elton API; ошибки, stale stock, pending/unknown payment и recovery отражаются честно.
- Финальная сумма/доступность приходит от API; не сохранять order/payment правду в localStorage.
- Admin API permission проверяется сервером, скрытая кнопка не является защитой.
- SEO: стабильные URL, canonical, metadata, sitemap, Product/Breadcrumb structured data только из достоверных данных; account/admin/checkout закрыты от индексации. Review markup не добавлять без проверки прав и актуальных требований источника.
- Публичные previews содержат синтетические данные; секреты не использовать в клиентских env.

## Первый пакет работы

После contract review сделать catalog/PDP/cart UI по API mocks, затем подключить к Elton API и PG. Сделать форму контактов/адреса и результат локальной заявки, minimal admin UI. Оплата/доставка отключены и честно обозначены в интерфейсе; provider flow, SMS и ЛК подключаются на следующем этапе. Демо не выдавать за принятие оплаты или одобрение подключения Ozon.

## Готовность

Responsive и accessibility проверены; SEO metadata/canonical корректны; события дедуплицируемы; сумма и статусы соответствуют API; нет прямых Ozon calls или merchant credentials в bundle.
