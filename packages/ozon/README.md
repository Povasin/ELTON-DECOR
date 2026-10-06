# Ozon adapters

Планируемый Python пакет adapters Seller/Performance/Pay/Delivery. Владелец Backend/Ozon; contract review Architect. Сейчас adapters не реализованы и real credentials не проверены.

Вход: [OZON_INTEGRATION](../../docs/OZON_INTEGRATION.md), [API](../../docs/API.md), [SECURITY](../../docs/SECURITY.md).

HTTP, timeouts/retry/rate limits, pagination, typed parsing/mapping и provider errors. Здесь нет pricing/bundle policy/return approval или core order transitions. External checkout работает через подтверждённый Pay/Delivery contract, не через произвольное создание FBO posting Seller API.
