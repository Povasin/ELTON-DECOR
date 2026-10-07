# API и worker entry points

Планируемое FastAPI/Pydantic приложение с core services, server auth, API для storefront/admin, webhook endpoints и worker entry points. Redis/Celery worker и scheduler запускаются отдельными процессами из той же кодовой базы. Сейчас implementation отсутствует.

Владелец: Backend/Ozon. Вход: [ARCHITECTURE](../../docs/ARCHITECTURE.md), [DATABASE](../../docs/DATABASE.md), [API](../../docs/API.md), [BUSINESS_RULES](../../docs/BUSINESS_RULES.md).

Core orchestration принимает бизнес-решения. External HTTP/mapping — `packages/ozon`; models/migrations — `packages/database`; event contracts/calculations — `packages/analytics`. PostgreSQL сохраняет orders/payment/refund truth; Redis не финансовый ledger. Provider endpoint/schema не угадывать.
