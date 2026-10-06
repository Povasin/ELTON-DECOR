# Analytics

Планируемые language-neutral event schemas и Python расчёты/marketplace imports. Владелец Backend/Ozon; Frontend отправляет события по согласованной schema. Реализации пока нет.

Вход: [ARCHITECTURE](../../docs/ARCHITECTURE.md), [API](../../docs/API.md), [BUSINESS_RULES](../../docs/BUSINESS_RULES.md), [QA](../../docs/QA.md).

Всегда отличать сайт от Ozon marketplace. Purchase/refund подтверждаются сервером; клиентский redirect не источник выручки. Event ID нужен для dedup, session/UTM данные не содержат телефонов/адресов. Economics из elton-dashboard-ai требуют Decimal и сверки ledger, не копируются как готовая формула прибыли сайта.
