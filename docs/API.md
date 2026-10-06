# Внутренний API Elton Decor

Дата: 2026-10-06. **Проект внутреннего контракта для Backend review**, endpoints не реализованы, не API Ozon. Base /api/v1; FastAPI/Pydantic генерирует OpenAPI и TS types. Основание BA-SCOPE-01/BR-27; версия входов — ARCHITECTURE §1. Этап 1 ниже имеет приоритет над сохранённым будущим inventory.

## Этап 1: транспорт, деньги и доверие

JSON UTF-8, UTC ISO-8601 timestamps, UUID local IDs. Money = `{amount_minor: string,currency:"RUB"}`, canonical decimal integer string без exponent/float; bigint boundary проверяется сервером. Quantity — integer в диапазоне 1…2147483647; умножение компонентов тоже ограничено этим диапазоном. Money amount_minor в диапазоне 0…9223372036854775807. Выход за диапазон →422 VALIDATION_ERROR до записи. Цена клиента никогда не доверенная. Null доставка не переводится в ноль. Cart/quote/result/admin: Cache-Control private,no-store. Public catalog первого slice no-store. X-Request-ID + trace_id в problem, PII не в URL/trace/logs.

**Рекомендованный local routing:** storefront http://localhost:3000 и admin http://localhost:3001 используют свои same-origin /api/v1 Next proxy к API http://127.0.0.1:8000. Browser не вызывает API другого origin. Proxy forwarding только к server-configured ELTON_API_URL, без client URL, с ограниченными methods/headers, сохранением Cookie/Set-Cookie, X-CSRF-Token и исходного Origin. Не подменяет Origin доверенным значением; не кэширует authenticated responses. API отдельно проверяет exact guest origin http://localhost:3000 и admin origin http://localhost:3001; preview origins задаются конкретно после hosting review, wildcard credentials запрещён. Direct browser CORS credentials по умолчанию отключён.

Cookie names elton_guest и elton_admin; Path=/api, HttpOnly, SameSite=Lax. Secure=true для HTTPS preview/live. Допустимое техническое исключение Secure=false только для explicit loopback development HTTP, запрещено на публичном preview. Cookies разделены именем/server scope, не портом: localhost:3000/3001 не являются изоляцией cookie. Trusted proxy настройки/forwarded headers фиксируются в запуске, не принимаются от произвольного клиента. CSRF проверяет Origin и bound server token на cookie mutations; CSRF token выдаётся no-store через GET /session и GET /admin/session, связывается с соответствующей live session (например HMAC с runtime SESSION_CSRF_KEY); это не guest proof. Секрет ключа не в коде/logs. POST guest-sessions/login до сессии требует разрешённый Origin/rate limit; logout/session rotation инвалидируют session-bound token.

Guest principal: random secret cookie, hash в PG, expires/revoked guards. Owner draft связан с guest session; GET чужой/неизвестный result одинаковый 404. Phone/UUID/query token не открывают результат. Demo срок 7 дней и quote 15 минут — предлагаемые конфигурируемые technical test values, не принятая production retention. Session GET возвращает csrf_token/expires_at, не raw auth token. Истечение → 401 SESSION_EXPIRED, не автопривязка по телефону. Admin permissions отдельные; ADM-01 login proposal ждёт согласования.

## Этап 1: inventory

Все пути ниже относительно /api/v1. UUID item paths — отдельные routes, brackets не используются как выдуманный endpoint.

| Method/path | Auth | DTO / эффект |
| --- | --- | --- |
| GET /capabilities | public | mode=foundation_demo; real_checkout/payment/delivery/stock_reservation/sms/customer_account/returns/refunds/reviews=false |
| GET /categories | public | CAT-01 categories; «Все товары» navigation, не отдельная сущность SKU |
| GET /products | public | items ProductSummary + next_cursor; demo q title/SKU, category slug, sort title_asc/price_asc/price_desc, limit default20 max100; candidate CAT-03/Q-09, final UX review |
| GET /products/by-slug/{slug} | public | ProductDetail по unique slug; route объявляется до UUID route |
| GET /products/{id} | public | ProductDetail, clean media, attributes/SEO, related products, bundle preview; cost/private media/provider credentials исключены |
| GET /collections; GET /collections/{id} | public | Статические связи CAT-04; not algorithmic recommendations |
| POST /guest-sessions | public Origin/rate limit | 201 new cookie or 200 existing live session (no unintended rotation), SessionDTO |
| GET /session | guest | SessionDTO with csrf_token/expires_at |
| GET /cart | guest | CartDTO, ETag decimal version quoted |
| PUT /cart/items/{product_id} | guest+CSRF+If-Match | {quantity:int}; positive, 0 rejected; 200 CartDTO/new ETag |
| DELETE /cart/items/{product_id} | guest+CSRF+If-Match | 200 CartDTO; missing item no-op if version current; no hard product deletion |
| POST /draft-quotes | guest+CSRF | {cart_version:int}; 201 DraftQuoteDTO. Server recomputes; empty/inactive/unpriced composition rejected |
| POST /checkout-drafts | guest+CSRF+Idempotency-Key | DraftSaveCommand → 201 DraftDTO; exact replay same 201/result with Idempotency-Replayed:true |
| GET /checkout-drafts/{id} | guest owner | immutable DraftDTO; foreign/unknown 404 |
| GET /admin/session | admin | admin identity/permissions + csrf_token; separate scope |
| POST /admin/auth/login; POST /admin/auth/logout | proposed ADM-01 | Login {email,password}; login strict Origin/rate limit, logout admin+CSRF. Not implemented until approval |
| GET /admin/products; GET /admin/products/{id} | admin catalog.read | ProductAdminDTO |
| POST /admin/products | admin catalog.write+CSRF | ProductWriteDTO →201 ProductAdminDTO |
| PATCH /admin/products/{id} | admin catalog.write+CSRF+If-Match | allowed fields only →200/new ETag; type change of referenced single to bundle rejected |
| PUT /admin/products/{id}/site-price | admin catalog.write+CSRF+If-Match | {price:Money}; server positive RUB demo policy, changes aggregate product version |
| GET /admin/products/{id}/bundle | admin catalog.read | BundleDTO |
| PUT /admin/products/{id}/bundle | admin catalog.write+CSRF+If-Match | {components:[{product_id,quantity}]}; proposed BR-12 validation → new immutable BOM/version, updates product version |
| POST /admin/products/{id}/media | admin catalog.write+CSRF+If-Match | multipart file, alt_text, position →201 MediaDTO only after complete validation/storage. URL import absent |
| DELETE /admin/products/{id}/media/{media_id} | admin catalog.write+CSRF+If-Match | unlink verified media, audit; previous draft has no promise to retain gallery URLs |
| GET /admin/checkout-drafts | admin drafts.read | cursor list summaries state=saved, created_from/to; no paid filters or revenue KPI |
| GET /admin/checkout-drafts/{id} | admin drafts.read | DraftAdminDTO including contact/address; audit read without copying PII |

Admin method без действующей admin session возвращает 401, без permissions/CSRF —403; будущая customer/guest cookie не даёт admin scope. Catalog writes используют единый product version, увеличиваемый при смене цены/BOM/media/content. Отсутствующий If-Match →428 PRECONDITION_REQUIRED; устаревший →409 VERSION_CONFLICT. Metadata length/page limits — предлагаемые технические ограничения, фиксируются в OpenAPI до реализации и не становятся дополнительной бизнес-политикой.

## Этап 1: DTO

Предложенный demo contact = {phone:string required, name:string|null, email:string|null}; address = {city:string required, address_line:string required, postal_code:string|null}. Лимиты строк: phone32/name120/email254/city120/address_line500/postal_code20; whitespace нормализуется, unknown keys отклоняются. Это предложенные поля локальной демонстрации для BA/Backend review; требования географии/PVZ/provider/customer profile ими не определяются. В допущенном demo используются синтетические входы; regex не доказывает отсутствие реальных PII. Тексты consent/условий обработки требуют отдельного утверждения.

ProductSummary = {id,sku,slug,title,type:single|bundle,price:Money,thumbnail:MediaDTO|null,availability:{state:"unknown",quantity:null,source:null,observed_at:null},version}. ProductDetail adds description, categories, attributes, seo, media[], related_product_ids[], bundle:BundleDTO|null, delivery:{state:"not_connected"}. ProductAdminDTO adds active and editable metadata, no fulfillment/paid switch. ProductWriteDTO accepts sku/slug/title/description/type/category_ids/attributes/seo/active; no monetary/provider states in arbitrary JSON. Collections/relations owned admin content may initially be seeded, their final editing UX Q-09 separate.

MediaDTO = {id,type:image|video,url,alt_text,position}; url server-selected relative public path only after clean validation. BundleDTO = {version_id,version,components:[{product_id,sku,title,quantity,base_unit_price:Money}]}; component prices informational, not net refund allocation.

CartDTO = {id,version,items:[{product_id,quantity,unit_price:Money|null,line_total:Money|null,issue:null|PRODUCT_INACTIVE|PRICE_MISSING|BUNDLE_INVALID}],goods_total:Money|null,can_quote:boolean,delivery:{state:"not_connected",amount:null},payable_total:null}. Существующая некорректная строка остаётся видимой с issue, чтобы её можно было удалить; при любой invalid/unpriced строке goods_total=null, без ложного частичного итога. Изменение цены каталога само не меняет cart version: quote отдельно проверяет catalog signature.

DraftQuoteDTO = {quote_id,cart_version,state:"valid",expires_at,items:[DraftLineSnapshot],goods_total:Money,delivery:{state:"not_connected",amount:null},payable_total:null,capabilities:{save_draft:true,pay:false,submit_delivery:false}}.
DraftLineSnapshot = {product_id,sku,title,quantity,unit_price:Money,line_total:Money,bundle_version_id:UUID|null,components:[{product_id,sku,title,quantity_per_bundle:int,total_quantity:int,base_unit_price:Money}]}.
Произвольные delivery_selection_ref/amount/price/stock/requested_state не принимаются.

DraftSaveCommand = {quote_id:UUID,contact:ContactDemo,address:AddressDemo}; Все поля входят в normalized request hash; цены/снимки из client body не доверенные. DraftDTO = {id,state:"saved",channel:"site",created_at,items:[DraftLineSnapshot],goods_total:Money,delivery:{state:"not_connected",amount:null},payable_total:null,contact:ContactDemo,address:AddressDemo,capabilities:{pay:false,cancel:false,return:false,submit_delivery:false},message:"Заявка сохранена; оплата и доставка пока не подключены"}.
DraftAdminDTO содержит те же frozen values и admin trace/audit context. goods_total=sum(top-level quantity×unit_price), base prices компонентов повторно не складываются. Saved DTO не содержит payment/fulfillment/refund state, provider IDs, reservation, ledger/purchase.

### Расчёт и повторы

Создание quote согласованно читает cart/catalog под блокировками, проверяет состав, сохраняет server snapshots/version signature/expiry. Новое сохранение сначала проверяет сессию и idempotency, затем owner/valid/unexpired quote, совпадение cart version/signature под PG locks; draft/snapshot/quote consumption/idempotency фиксируются атомарно (DATABASE). Replay проверяет owner и возвращает существующий снимок до consumed/expiry/cart/catalog guards: потерянный успешный ответ не превращается в недопустимый запрос. Тот же key с другим normalized body →409 IDEMPOTENCY_CONFLICT. Новый key с consumed quote →409 QUOTE_USED. Устаревшая cart →409 CART_CHANGED; изменённые price/title/BOM/component price/activity →409 QUOTE_CHANGED; истёкший quote →410 QUOTE_EXPIRED. Конфликт не сохраняет замену автоматически: пользователь получает fresh cart/quote и подтверждает новый key.

Клиент создаёт один случайный UUID Idempotency-Key на подтверждённое сохранение, удерживает его до восстановления ответа и повторяет идентичные body/key после transport/503 failures. Ключ операции может храниться в sessionStorage; authentication cookie никогда не попадает в localStorage/URL. Для первого synthetic demo после технического review сохранять pending normalized DraftSaveCommand + тот же Idempotency-Key в sessionStorage на срок не более 1 часа; это содержит только синтетические контакты и адрес, не auth cookie. После definitive result/error удалить body; successful draft ID сохранить для result route. При full reload до ответа повторять exact body/key, не создавать новый ключ. Если local pending record истёк/недоступен, UI не делает новый save автоматически и не заявляет отказ предыдущей операции. Для реальных PII этот browser recovery способ не разрешён: потребуется отдельный data/recovery design. Страница результата восстанавливается с persistent cookie и result ID. При timeout UI показывает ожидание сохранения/проверки повтора; оплата/отказ покупки не заявляются. Потеря cookie требует новой сессии и не позволяет восстановить прежнюю заявку по телефону.

## Этап 1: ошибки и disabled routes

problem+json = {type:"urn:elton:problem:<code>",title,status,code,detail,trace_id,retryable}. PII/raw payload в detail запрещены. 400/422 VALIDATION_ERROR; 401 SESSION_REQUIRED/SESSION_EXPIRED; 403 FORBIDDEN/CSRF_REJECTED; 404 NOT_FOUND; 409 CART_CHANGED/QUOTE_CHANGED/QUOTE_USED/VERSION_CONFLICT/IDEMPOTENCY_CONFLICT; 410 QUOTE_EXPIRED; 428 PRECONDITION_REQUIRED; 429 RATE_LIMITED (Retry-After); 503 STORAGE_TEMPORARILY_UNAVAILABLE (retryable true, retry same key). 201 подтверждает **локальное сохранение**; внешней операции нет. Этап 1 не возвращает 202 processing payment.

Будущие commands /checkout/quotes, POST /orders, /orders/{id}/payment-attempts, cancellation-requests, returns, /auth/sms/challenges, /auth/sms/verify, /me routes, /return-photo-uploads, /admin/returns/{id}/refund-requests и reconciliation не включены. Известные disabled routes возвращают 409 CAPABILITY_DISABLED после session/permission checks; без прав 401/403. Public SMS start возвращает disabled без отправки. Незарегистрированный route →404. Provider callback не зарегистрирован, возвращает 404 без acknowledgement внешнего эффекта. Тесты доказывают zero external calls и отсутствие financial/entity/event writes; одной отключённой кнопки недостаточно. Неизвестные endpoints Ozon не придумываются.

## Предложение проверки медиа

Только файлы: JPEG/PNG/WebP до 10 MiB, после decode dimension≤8192/pixels≤40 million; MP4 до 50 MiB/60 sec с проверкой metadata/container/codec до включения. Это рекомендации demo, фиксируются review/OpenAPI. При отсутствующем decoder/video pipeline capability недоступна, непроверенные bytes не публикуются. Сервер считает streamed bytes, отвергает поддельные MIME/extension, decompression bombs, traversal, SVG/HTML/scripts/polyglots. Raster derivatives очищаются от EXIF, nosniff/correct Content-Type обязательны. Quarantine вне web-root, UUID path; полная validation предшествует clean/public/audit DB pointer. Ошибка не оставляет публичный ref; локальная безопасная очистка orphan без обязательного Celery. URL import отложен (SSRF), private return photos — этап 2.

## Проверки этапа 1

Проверяются на actual PG: atomic retry/concurrency, key mismatch, replay после expiry, новый key consumed quote, rollback при сбое до commit, price/BOM изменения/immutable snapshot, bigint/quantity overflow, inactive/deleted items, чужой ID/session expiry, admin scope/CSRF/version, upload spoof/limits, fail-closed commands с zero provider calls/facts. Настоящий browser→same-origin proxy→API→PG E2E подтверждает cookie persistence и permissions. OpenAPI TS generation/checks исключают неактивные будущие endpoints. Тесты пока не созданы и не пройдены.

## Этап 2: сохранённый предложенный API (disabled)

Ниже целевой коммерческий inventory и DTO только для будущего provider/business/release review. Его presence не означает endpoint support сейчас. ADM-01 approval, BR-15, profile/claim policy и Ozon gates остаются обязательными для зависимых реализаций. Commercial quote examples допустимы только с проверенным тарифом; unknown всегда nullable, не бесплатный synthetic default.

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
  "delivery": {"amount_minor": "15000", "currency": "RUB"},
  "total": {"amount_minor": "44000", "currency": "RUB"},
  "availability": {"state": "observed_available", "observed_at": "2026-10-06T12:00:00Z"}
}
```

Quote expiry/timing и ненулевой пример тарифа — synthetic; реальные значения только из проверенного коммерческого контракта. `availability` не обещает Ozon reservation. Возможные состояния: `observed_available`, `unavailable`, `stale`, `unknown`; UI wording согласовать.

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
