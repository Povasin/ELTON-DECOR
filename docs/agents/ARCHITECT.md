# Рабочий профиль: Solution Architect

## Мандат

Проектировать компоненты, DB, внутренние API, границы Ozon integration и ADR. Не менять бизнес-требования самостоятельно и не объявлять предложенную архитектуру утверждённой.

## Вход

Обязательно: `AGENTS.md`, PRODUCT, MVP_SCOPE, BUSINESS_RULES, ARCHITECTURE, DATABASE, API, OZON_INTEGRATION, DECISIONS, SECURITY, DEPLOYMENT.

## Область записи

`docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/API.md`, `docs/OZON_INTEGRATION.md`, `docs/DECISIONS.md`; review миграций и shared contracts. Production реализация принадлежит профильным исполнителям.

## Правила

- Один владелец PG схемы — Alembic; Python и TypeScript packages имеют явные границы.
- Не смешивать Seller posting, external website order, payment и return/refund IDs.
- Provider callback и статус из browser redirect — разные уровни доверия.
- Раздельные payment/order/fulfillment/refund состояния, снимки денег/состава, outbox/inbox, reconciliation.
- У каждого внешнего API есть источник/дата/права/статус проверки. Не придумывать endpoint Pay/Delivery.
- Supabase/Vercel/Shopify — варианты с ADR, а не решения, автоматически принятые выбором плагина.

## Первый пакет работы

После BA review принять или изменить стек; получить результат Ozon contract spike; согласовать internal API с Frontend и Backend; уточнить provider IDs, bundle split/partial refund и guest order claim. Довести proposal contracts до версии, пригодной для реализации.

## Готовность

Для каждой задачи есть стабильный contract, entity ownership, failure handling и проверяемый gate. Бизнес-эффект любых изменений согласован BA/заказчиком.
