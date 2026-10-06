# Admin

Планируемое отдельное приложение Next.js / TypeScript: dashboard, товары/цены сайта/bundles, заказы, возвраты, history. Сейчас runtime не создан.

Владелец UI: Frontend; admin API/расчётов: Backend/Ozon. Вход: [PRODUCT](../../docs/PRODUCT.md), [API](../../docs/API.md), [SECURITY](../../docs/SECURITY.md).

Один защищённый admin, email/password/server session; permission checks в API. Статус fulfillment поступает от provider, не редактируется руками. Marketplace/site показатели разделены; публичный prototype elton-dashboard-ai не является готовой web админкой.
