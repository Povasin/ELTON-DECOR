# Журнал решений

Дата базовой подготовки: 2026-10-06. «Принято для документации» определяет устройство этого набора файлов; не означает production approval всей архитектуры.

| ADR | Решение | Статус | Основание / последствия |
|---|---|---|---|
| ADR-001 | Один monorepo и `/docs` как источник истины | принято для документации | явное указание заказчика; чаты не заменяют спецификацию |
| ADR-002 | Пять рабочих профилей; специализированные роли распределены | принято для документации | BA, Architect, Frontend, Backend/Ozon, QA/DevOps |
| ADR-003 | Next.js/TS витрина и admin; FastAPI/Python API | предложено | Python economics prototype полезен backend; два frontend приложения используют общую UI library |
| ADR-004 | PostgreSQL, SQLAlchemy/Alembic; Redis/Celery | предложено; обязательность Redis/Celery для bootstrap superseded by ADR-012/013 | PG/Alembic основа; Redis/Celery и коммерческие таблицы только при соответствующих задачах этапа 2 |
| ADR-005 | Guest checkout, SMS для покупателя; предложен отдельный admin email/password/server session | guest/SMS подтверждены; метод admin auth предложен | согласовать ADM-01 до реализации; менять customer flow на обязательную регистрацию/OAuth нельзя без BA change |
| ADR-006 | Seller API и внешний checkout — разные contracts | техническое ограничение | FBO posting list не доказывает создание заказов сайта; Pay/Delivery spike обязателен |
| ADR-007 | Нельзя считать локальную бронь бронью FBO | техническое ограничение | общие stocks изменяются вне сайта; provider authoritative availability/commit нужен |
| ADR-008 | Стек hosting и регион хранения | открыто | Vercel frontend и Supabase PG/Storage — кандидаты; production PII/data placement требует решения; Shopify — только альтернативная платформа |
| ADR-009 | elton-dashboard-ai — прототип для выборочного reuse | предложено | экономические формулы/репорты после сверки; не готовая админка, auth или core orders |
| ADR-010 | AI из Gemini cookbook вне MVP core | предложено | V2 помощник с tool permissions; без права самостоятельно платить/менять цены/возвращать деньги |
| ADR-011 | Bundles fulfillment, discount allocation и refunds | предложенный алгоритм; provider gate открыт | состав и правила в BUSINESS_RULES; транспорт/частичный refund подтверждаются контрактом |
| ADR-012 | Два этапа: локальная основа сейчас, реальная оплата/доставка позже | подтверждено заказчиком 2026-10-06 (BA-SCOPE-01) | BR-27/S1-01…06; supersedes прежнюю зависимость витрины/основы от полного коммерческого checkout; не подтверждает stack/auth/TTL/hosting/provider approval |
| ADR-013 | Отдельный immutable checkout_draft, server guest cart/owner proof, nullable delivery, минимальный PG bootstrap | проект Architect; Backend review до реализации | внутренние DB/API рекомендации этапа 1, не customer approval; finance/provider state не симулируются |

## ADR-012 — scope первого этапа

- **Дата/автор:** 2026-10-06, BA фиксирует явное решение заказчика, Architect отражает его технические последствия.
- **Контекст:** исходная база требовала commercial checkout до готовности MVP. Заказчик просит подготовить магазин для демонстрации/начала подключения Ozon, отложив реальную оплату и доставку.
- **Варианты:** ждать verified Pay/Delivery перед всей витриной; создать локальную основу первым этапом.
- **Решение/статус:** заказчиком выбран второй вариант, BA-SCOPE-01, PRODUCT/MVP_SCOPE/BUSINESS_RULES BR-27; исходные 25 IDs и BR-01…26 сохранены. Это утверждение scope, не endorsement конкретной реализации.
- **Последствия:** storefront/PDP/server guest cart/contact/address/local saved result/minimal protected admin сейчас; SMS/ЛК/оплата/статусы/возвраты/FBO/reviews после своих gates. Unknown delivery нельзя заменить 0; preview synthetic. Ozon gate не блокирует bootstrap, ADM-01/security всё ещё блокируют соответствующие зависимые функции.
- **Evidence/review:** явное решение заказчика от 2026-10-06 → BA FREEZE; Architect проверяет соответствие DB/API. Список обязательных документов Ozon/его одобрение этим решением не установлены.

## ADR-013 — технический дизайн foundation

- **Дата/автор:** 2026-10-06, Solution Architect. **Статус: proposed technical design, требуется Backend review перед implementation; customer approval не заявлен.**
- **Контекст:** BR-27 требует настоящие PG persistence/immutable snapshots/owner access/idempotency без внешних эффектов.
- **Варианты:** переиспользовать commercial orders с ложными payment/fulfillment defaults; отделить demo draft aggregate. Выбранная рекомендация — отдельные cart/draft_quote/checkout_draft и items/components, state только saved, no commercial table dependency. Полный customer schema и Redis/Celery откладываются.
- **Interfaces:** API first-stage inventory и exact DTO — API.md; migration groups/transaction — DATABASE.md. goods_total только товарная сумма; delivery.amount/payable_total null. Freeze BOM quantities/base prices без BR-15 refund allocation. Idempotency/quote consumption/immutable snapshots одним PG commit; replay before quote expiry. Будущий commercial promotion только отдельным согласованным fresh-confirmed command, без auto submission.
- **Trust:** persistent random HttpOnly guest cookie, PG token hash/owner/expiry; no ID/phone access. Same-origin Next proxy/local exact Origin+CSRF, отдельный server admin scope. ADM-01 остаётся proposed до approval, как ADR-005.
- **Technical demo recommendations:** session7 days/quote15 minutes, positive RUB siteprice, proposed contact/address DTO и media limits; фиксируются review/config/OpenAPI, не становятся утверждёнными retention/нулевыми ценами/provider правилами. File-only media validation/quarantine, no URL import SSRF. Hosting не выбран.
- **Consequences/review owner:** Backend/Ozon проверяет constraints/races/request hash; Frontend проверяет proxy/cookie/nullable totals/UI; QA проверяет actual PG/browser fail cases. План [stage1-foundation](superpowers/plans/2026-10-06-stage1-foundation.md) исполняется после review зависимых решений. Следующее документное изменение должно явно обновить ADR/DB/API, не молча принять policy.

## Открытые решения для основы

ADM-01 блокирует реализацию входа/полную S1-05, но не подготовку плана/каталога/cart/draft. Final CAT-03/Q-09/content, technical demo TTL/contact/address/positive-price/media recommendations требуют профильного review; это не требование provider API. Public preview/live PII требуют hosting/region/security/data release gate. BR-15, guest SMS claim, stale stock/резервы/refund policies — этап 2. Supabase/Vercel лишь hosting candidates; SupabaseAuth/Shopify second order authority не включаются.

## Как добавить ADR

Указать ID, дату, автора роли, контекст, варианты, выбранный вариант, влияние на требования/контракты, статус, evidence и owner review. Старые решения не удалять: отмечать `superseded by ADR-...`. Пока owner не назначен человеком, указывать роль, а не придумывать имя.

## Открытые решения до коммерческой оплаты этапа 2

1. Ozon Pay/Delivery entitlement продавца и живой контракт (external order, stock, callbacks, cancel, partial refund, fiscalization).
2. Возможность передачи bundle-компонентов и исполнения без самостоятельного bundle SKU.
3. Доступ/публикация Ozon отзывов и медиа.
4. Provider SMS, правила привязки гостевых заказов и recovery; лимиты/TTL после security review.
5. Фактический hosting, region, backup/restore и требования к персональным данным.
6. Операционная процедура возврата товара и денег, суммы/логистика/сроки; не выдавать предложения за правила заказчика.
