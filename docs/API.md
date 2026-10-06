# Внутренний API Elton Decor

Дата: 2026-10-06. Статус: **предложенный контракт нашего API**, не работающие endpoints и не API Ozon. Base path `/api/v1`; FastAPI/Pydantic генерирует OpenAPI, frontend получает TS types. Внешний контракт проверяется отдельно в [OZON_INTEGRATION.md](OZON_INTEGRATION.md).

Трассировка: CAT-01–06, ORD-01–05, ACC-01–03, RET-01–03, ADM-01–08 из [PRODUCT.md](PRODUCT.md); business invariants BR-01–26 из [BUSINESS_RULES.md](BUSINESS_RULES.md). Наличие строки в этом документе не превращает условное требование в подтверждённое.

## 1. Общие правила

HTTP JSON UTF-8, UTC ISO-8601 timestamps, UUID локальных сущностей, непрозрачные строковые provider IDs. Money: `{"amount_minor":"12345","currency":"RUB"}`; integer minor units передаются строкой, расчёт суммы всегда серверный. Количество — положительное integer. Client не передаёт цену как доверенный факт.

Cursor pagination: `?cursor=<opaque>&limit=20`, server limit bounded; response `items`, `next_cursor`. Разрешённые sort/filter enum фиксируются OpenAPI по согласованным CAT-03, без произвольных SQL полей. Все response содержат/дублируют trace ID в `X-Request-ID`; PII не попадает в URL/query/logs.

Errors используют `application/problem+json`:

```json
{
  "type": "urn:elton:problem:quote-changed",
  "title": "Условия заказа изменились",
  "status": 409,
  "code": "QUOTE_CHANGED",
  "detail": "Пересчитайте заказ перед оплатой",
  "trace_id": "synthetic-trace",
  "retryable": false
}
```

| HTTP | Значение |
|---|---|
| 400/422 | Некорректные параметры/валидация |
| 401 | Нет действующей сессии |
| 403 | Нет разрешения на действие; admin CSRF failure |
| 404 | Объект отсутствует или не принадлежит покупателю (защита enumeration) |
| 409 | Conflict/version mismatch/idempotency mismatch/state guard |
| 410 | Истёк quote/challenge/capability, если disclosure допустим |
| 429 | Лимит запросов; `Retry-After` |
| 503 | Провайдер временно недоступен до начала операции; `retryable` по taxonomy |
| 202 | Операция принята локально, её внешнее завершение ещё не подтверждено |

Timeout после внешней mutation не превращается в простой 503 с предложением повторить оплату: operation становится `unknown`, UI получает существующую operation и polling.

## 2. Авторизация и идемпотентность

Публичные GET catalog не требуют сессии. Cart и guest checkout используют HttpOnly Secure cookie со случайным guest session token. Покупатель имеет отдельную customer session после SMS; admin — отдельную server session email/password. Все cookie-auth mutations защищены от CSRF и проверяют Origin. Exact origins/hostnames выберутся при hosting; wildcard credentials запрещён.

Guest order access — capability с высокой энтропией, server хранит hash. Токен приходит через защищённый flow и меняется на cookie; не класть его в analytics/referrer. Номер заказа, телефон и provider ID не позволяют открыть заказ. После SMS нельзя автоматически прикрепить все совпавшие телефонные заказы: нужен доказанный guest capability/ownership flow (BR-05, решение открыто).

Для ORD-01 guest cart использует persistent cookie и PG storage, срок согласуется Q-06. После SMS verification слияние cart выполняет server по согласованному BR-06, повторный login не сливает одно количество второй раз; merge marker/version фиксируются транзакционно. Сам алгоритм количества/приоритета пока не принят. Profile address DTO/PUT ниже — предложение одного адреса; уточнение объема ACC-02 из MVP_SCOPE требуется перед реализацией.

Checkout, payment retry, cancel, return submit и refund используют обязательный `Idempotency-Key`. Scope = principal/guest session + endpoint operation. Сервер сохраняет hash body и результат в PG; повтор того же body возвращает ту же сущность, другой body → `409 IDEMPOTENCY_CONFLICT`. Replay тоже проверяет authorization. Клиент сохраняет ключ до terminal result. Provider key/retention не предполагаются равными локальным: соответствие хранит adapter.

Редактирование каталогов/решение возврата используют `ETag`/`If-Match` version; stale write → 409 `VERSION_CONFLICT`. Идемпотентность и version lock решают разные задачи.

## 3. Endpoint inventory

| Method / path | Auth | Назначение / результат |
|---|---|---|
| GET `/categories` | public | Согласованные категории CAT-01 |
| GET `/collections[/{id}]` | public | Подборки CAT-04; фактически раздельные collection/list routes; final composition/UX Q-09 |
| GET `/products` | public | Каталог, поиск/фильтры/сортировка CAT-03 по финальному набору параметров |
| GET `/products/{id}` | public | Product, site money, images, type, bundle preview, availability/freshness |
| GET `/products/{id}/reviews` | public | Только разрешённые синхронизированные отзывы; feature flag/gate CAT-06 |
| POST `/guest-sessions` | public + rate limit | Создать гостевую session cookie; не регистрация |
| GET `/cart` | guest/customer | Server cart + version + текущая оценка суммы |
| PUT `/cart/items/{product_id}` | guest/customer | `{quantity}`; 0 запрещён, удаление отдельным DELETE |
| DELETE `/cart/items/{product_id}` | guest/customer | Удалить позицию |
| POST `/checkout/quotes` | guest/customer | Рассчитать immutable quote, доставка условна ARCH-G1 и ARCH-G2 |
| POST `/orders` | guest/customer | Idempotent checkout из quote; 202 order/operation |
| GET `/operations/{id}` | owner/admin | Текущий status/result без raw provider payload |
| GET `/orders/{id}` | order owner/capability/admin | Order snapshot + независимые состояния |
| POST `/orders/{id}/payment-attempts` | owner/capability | Новый attempt только если прежний подтверждён failed/cancelled и условия ещё допустимы |
| POST `/orders/{id}/cancellation-requests` | owner/capability | `{reason}`; запрос отмены ACC-03; 202, provider capability guard |
| POST `/auth/sms/challenges` | public + rate limit | Телефон, generic response, challenge id, resend_after |
| POST `/auth/sms/verify` | challenge + rate limit | Проверка кода, rotation customer session cookie |
| POST `/auth/logout` | customer | Revoke current session |
| GET/PATCH `/me` | customer | Профиль по согласованным полям; смена телефона/email закрыта Q-06, отдельный verification flow ещё не утверждён |
| GET/PUT/DELETE `/me/address` | customer | Один profile address; order snapshots не меняются |
| GET `/me/orders` | customer | Только доказанно принадлежащие заказы |
| POST `/me/order-claims` | customer + guest proof | Подтверждённая привязка заказа; точный UX/метод доказательства открыт |
| POST `/orders/{id}/returns` | owner/capability | Заявка с позициями, qty, причиной, суммой, photo refs; BR-20–21 |
| GET `/orders/{id}/returns` | owner/capability/admin | История заявок и решений |
| POST `/return-photo-uploads` | order owner/capability | Grant для private upload, bound to order/session |
| POST `/return-photo-uploads/{id}/complete` | upload owner | Проверка object metadata, quarantine/scan; photo ref после проверки |
| POST `/admin/auth/login` | public + strict rate limit | Email/password → admin server session cookie |
| POST `/admin/auth/logout` | admin | Revoke session |
| GET `/admin/dashboard` | admin | Согласованные summary; схемы KPI открыты, totals раздельно по channel |
| GET `/admin/orders` | admin | Поиск/фильтры локальных order DTO, channel явно |
| POST `/admin/orders/search` | admin | Чувствительные фильтры ADM-03, включая телефон, в body с log redaction; не в URL |
| GET `/admin/returns` | admin | Очередь и фильтры заявок |
| POST `/admin/returns/{id}/decisions` | admin | approve/reject + mandatory rejection reason; version guard |
| POST `/admin/returns/{id}/refund-requests` | admin | Условный финансовый command, только после решения/проверки лимитов и contract gate |
| GET/POST/PATCH `/admin/products[/{id}]` | admin | SKU/контент; API фактически раздельные collection/item routes |
| PUT `/admin/products/{id}/site-price` | admin | Ручная цена сайта BR-09, money + change reason если согласовано |
| PUT `/admin/products/{id}/cost` | admin | Ручная себестоимость ADM-05, money + effective date; public product её не выдаёт |
| GET/PUT `/admin/products/{id}/bundle` | admin | Versioned components; provider gate перед публикацией продажи |
| GET `/admin/stock-snapshots` | admin | Provider/model/age/semantics; не ручное изменение FBO |
| GET `/admin/products/{id}/price-history` | admin | Глубина ADM-08 открыта; feature может быть условной |
| POST `/admin/operations/{id}/reconcile` | admin | Аудируемая постановка сверки; не ручное выставление fulfillment state |

Отдельного endpoint «изменить статус доставки» нет: ORD-05/BR-16. V2 endpoints favorites/OAuth/loyalty/blog/AI пока не проектируются. CSV/Excel export, ручной refund произвольного payment и массовые действия не подразумеваются этим inventory.

## 4. Quote и checkout DTO

POST `/checkout/quotes`:

```json
{
  "cart_version": 4,
  "delivery_selection_ref": "opaque-provider-choice",
  "contact": {"phone": "+70000000000", "email": "buyer@example.invalid"}
}
```

`delivery_selection_ref` — **внутренний проект** ссылки на выбор доставки; форма/address/PVZ/нужные contact поля определятся provider contract и бизнес-решением. Синтетические примеры не являются реальными контактами. Quote response:

```json
{
  "quote_id": "00000000-0000-4000-8000-000000000001",
  "version": 1,
  "expires_at": "2026-10-06T12:10:00Z",
  "items": [{"product_id": "00000000-0000-4000-8000-000000000002", "quantity": 1,
    "net": {"amount_minor": "29000", "currency": "RUB"}}],
  "delivery": {"amount_minor": "0", "currency": "RUB"},
  "total": {"amount_minor": "29000", "currency": "RUB"},
  "availability": {"state": "observed_available", "observed_at": "2026-10-06T12:00:00Z"}
}
```

Quote expiry/timing и пример бесплатной доставки — synthetic. `availability` не обещает Ozon reservation. Возможные состояния: `observed_available`, `unavailable`, `stale`, `unknown`; UI wording согласовать.

POST `/orders` с `Idempotency-Key` принимает `quote_id`, `quote_version`. Перед commit сервер проверяет quote lifetime, cart version, цены, component mappings и stock policy. Изменённые условия возвращают 409 с новым quote/причиной; не списывать другую сумму незаметно. Валидный ответ:

```json
{
  "order_id": "00000000-0000-4000-8000-000000000003",
  "operation_id": "00000000-0000-4000-8000-000000000004",
  "status": "processing",
  "payment_action": null
}
```

GET operation возвращает `processing|requires_action|succeeded|failed|unknown`, `order_id`, допустимый `payment_action` и code. Это операционные состояния HTTP команды, а не новые business states. `payment_action` содержит только разрешённый server-side redirect URL провайдера/SDK token согласно проверенному контракту; произвольный callback/return URL от client запрещён. `succeeded` operation означает завершение конкретного шага, не доставку заказа.

## 5. Order response и отмена

```json
{
  "id": "00000000-0000-4000-8000-000000000003",
  "number": "SYNTHETIC-ORDER",
  "channel": "site",
  "lifecycle_state": "placed",
  "attention_required": false,
  "payment": {"state": "succeeded", "captured": {"amount_minor": "29000", "currency": "RUB"}},
  "fulfillments": [{"state": "packing", "updated_at": "2026-10-06T12:05:00Z"}],
  "refund_summary": {"succeeded_minor": "0", "pending_minor": "0", "currency": "RUB"},
  "capabilities": {"request_cancel": false, "request_return": false},
  "items": []
}
```

State sets описаны DATABASE. Capabilities вычисляет backend с учётом provider contract, actual state и согласованной return policy, а не только кнопки UI. `request_cancel=true` означает доступность подачи запроса; окончательная отмена требует provider verification. При уже captured payment API показывает refund отдельно. Итог частичных fulfilments нельзя вычислять по первой posting.

## 6. Возврат и фото

POST `/orders/{id}/returns`:

```json
{
  "items": [{"order_item_id": "00000000-0000-4000-8000-000000000005", "quantity": 1}],
  "reason": "Описание покупателя",
  "requested_amount": {"amount_minor": "9667", "currency": "RUB"},
  "photo_ids": ["00000000-0000-4000-8000-000000000006"]
}
```

Server проверяет ownership, quantities/previous requests, photo ownership и `scan_state=clean`, monetary ceiling по frozen allocations. Bundle component identifier принимается только при согласованной возможности частичного возврата. Нельзя менять `order_item_id` на SKU другого заказа. Requested amount — заявка; confirmed refund amount всегда отдельная запись. Количество/обязательность фото и причина покупателя окончательно задаются PRODUCT/BUSINESS_RULES, размер/count uploads — инженерные лимиты до согласования.

Admin decision принимает `{decision:"approve"|"reject", reason:...}`; reject без nonblank reason → 422. Повтор несовместимого решения/старый version → 409. Approved не означает `refund.succeeded`. Refund request возвращает 202 operation и computed allocation; без подтверждённого контракта endpoint закрыт feature gate. Photo GET/signed URL разрешён только owner/admin; object keys и public bucket URLs не возвращаются посторонним.

## 7. Provider ingress и internal tasks

Route **нашего** callback ingress выбирается при регистрации интеграции; конкретный путь, метод, schema, signature headers и ответ задаёт provider contract. Он не является клиентским order endpoint. До gate не публиковать выдуманный `/ozon/...` как документацию провайдера.

Ingress сохраняет verified inbox event; duplicates обрабатываются идемпотентно. Недостоверная подпись — отклонение и журнал без raw секретов. Сверка внешнего object перед применением state обязательна при неоднозначности/требовании контракта. GET callback/redirect от browser никогда не заменяет verified provider fact.

Worker tasks не доступны публичному client: process outbox, apply inbox, reconcile operation, refresh stock, sync fulfilments, optionally sync permitted reviews. Manual reconcile только admin use case с audit. Celery task ID не financial idempotency key.

## 8. Contract tests перед реализацией

Проверить OpenAPI consumer generation; деньги без float; IDOR/guest capability; CSRF и разные session scopes; checkout key reuse/mismatch; lost provider response; callback replay/out-of-order; overselling локальных компонентов; двойной partial refund; upload ownership/quarantine. Provider fixtures соответствуют реальному sandbox, очищены от PII. Не выдавать mock checkout за end-to-end рабочую Ozon integration.
