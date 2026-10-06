# Журнал решений

Дата базовой подготовки: 2026-10-06. «Принято для документации» определяет устройство этого набора файлов; не означает production approval всей архитектуры.

| ADR | Решение | Статус | Основание / последствия |
|---|---|---|---|
| ADR-001 | Один monorepo и `/docs` как источник истины | принято для документации | явное указание заказчика; чаты не заменяют спецификацию |
| ADR-002 | Пять рабочих профилей; специализированные роли распределены | принято для документации | BA, Architect, Frontend, Backend/Ozon, QA/DevOps |
| ADR-003 | Next.js/TS витрина и admin; FastAPI/Python API | предложено | Python economics prototype полезен backend; два frontend приложения используют общую UI library |
| ADR-004 | PostgreSQL, SQLAlchemy/Alembic; Redis/Celery | предложено | транзакции/снимки/ledger, фоновые sync и reconciliation; Alembic — один owner схемы |
| ADR-005 | Guest checkout, SMS для покупателя; предложен отдельный admin email/password/server session | guest/SMS подтверждены; метод admin auth предложен | согласовать ADM-01 до реализации; менять customer flow на обязательную регистрацию/OAuth нельзя без BA change |
| ADR-006 | Seller API и внешний checkout — разные contracts | техническое ограничение | FBO posting list не доказывает создание заказов сайта; Pay/Delivery spike обязателен |
| ADR-007 | Нельзя считать локальную бронь бронью FBO | техническое ограничение | общие stocks изменяются вне сайта; provider authoritative availability/commit нужен |
| ADR-008 | Стек hosting и регион хранения | открыто | Vercel frontend и Supabase PG/Storage — кандидаты; production PII/data placement требует решения; Shopify — только альтернативная платформа |
| ADR-009 | elton-dashboard-ai — прототип для выборочного reuse | предложено | экономические формулы/репорты после сверки; не готовая админка, auth или core orders |
| ADR-010 | AI из Gemini cookbook вне MVP core | предложено | V2 помощник с tool permissions; без права самостоятельно платить/менять цены/возвращать деньги |
| ADR-011 | Bundles fulfillment, discount allocation и refunds | предложенный алгоритм; provider gate открыт | состав и правила в BUSINESS_RULES; транспорт/частичный refund подтверждаются контрактом |

## Как добавить ADR

Указать ID, дату, автора роли, контекст, варианты, выбранный вариант, влияние на требования/контракты, статус, evidence и owner review. Старые решения не удалять: отмечать `superseded by ADR-...`. Пока owner не назначен человеком, указывать роль, а не придумывать имя.

## Открытые решения до оплаты в MVP

1. Ozon Pay/Delivery entitlement продавца и живой контракт (external order, stock, callbacks, cancel, partial refund, fiscalization).
2. Возможность передачи bundle-компонентов и исполнения без самостоятельного bundle SKU.
3. Доступ/публикация Ozon отзывов и медиа.
4. Provider SMS, правила привязки гостевых заказов и recovery; лимиты/TTL после security review.
5. Фактический hosting, region, backup/restore и требования к персональным данным.
6. Операционная процедура возврата товара и денег, суммы/логистика/сроки; не выдавать предложения за правила заказчика.
