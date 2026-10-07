# Ozon adapters

`elton_ozon` — узкий server-only Python adapter для **read-only** Seller API.
Он принимает `SellerCredentials` только из runtime secret store и поддерживает
фиксированные POST paths: product list, product info list, stock snapshot и
review list. Он не содержит FastAPI routes, CLI sync, database import, worker,
Pay, Delivery, Performance client, FBO posting/order или browser configuration.

Контракт и evidence: [OZON_INTEGRATION](../../docs/OZON_INTEGRATION.md),
[DECISIONS](../../docs/DECISIONS.md), [API](../../docs/API.md),
[SECURITY](../../docs/SECURITY.md). Пагинационные cursors opaque; stock/review
observations не дают checkout availability или разрешения на публикацию отзывов.

Проверка пакета из корня репозитория:

```powershell
$env:PYTHONPATH = "packages/ozon/src"
.venv\Scripts\python.exe -m pytest packages/ozon/tests -q
```
