# Рабочий профиль: Backend / Ozon / Analytics

## Мандат

Core API, PG, auth, carts/orders/bundles/returns, adapters и worker; серверная аналитика сайта и import marketplace метрик. Не менять UI и не изменять правила заказчика.

## Вход

Обязательно: `AGENTS.md`, PRODUCT, MVP_SCOPE, BUSINESS_RULES, ARCHITECTURE, DATABASE, API, OZON_INTEGRATION, DECISIONS, SECURITY, QA. Для эксплуатации — DEPLOYMENT.

## Область записи

`apps/api/`, `packages/database/`, `packages/ozon/`, `packages/analytics/`. API/DB changes сначала документируются с Architect review. Эти области выполняются отдельными задачами: один исполнитель не означает смешение слоёв.

## Разделение модулей

- Core определяет снимок заказа, business transitions, bundle allocation, claim/access, return approval.
- Ozon adapter выполняет HTTP, pagination, rate limits, token expiry, parse/normalize, классификацию ошибок. Он не принимает бизнес-решения.
- Worker выполняет sync, outbox delivery, verified status reconciliation и отчёты с идемпотентными handlers.
- Analytics отделяет `site` от `marketplace`; расчёт прибыли требует сверки ledger и согласованных формул.

## Правила

Никакого float для денег; не сохранять пустой ответ `{}` как успешный результат интеграции. Повтор unknown операции с новым ключом запрещён до reconciliation. Локальные reservations не гарантируют FBO stock. Перед реализацией Pay/Delivery подтвердить entitlement/contract, callbacks, cancellation, refund и bundles.

Seller/Performance read credentials, Pay/Delivery credentials и SMS credentials хранятся отдельно. SQLAlchemy/Alembic — единый владелец схемы; Supabase Data API не становится обходом core API.

## Первый пакет работы

Ozon contract spike и sanitised evidence. Затем core catalog/cart/auth/order/payment states с deterministic fake provider для tests. Реальный adapter включать только по закрытым gates; admin status actions не меняют provider status вручную.

## Готовность

Integration/contract tests, money invariants, access control, idempotent callbacks и reconciliation подтверждены. Секретов/PII в fixture/log нет. Prototype economics из elton-dashboard-ai перенесён только после финансовой сверки.
