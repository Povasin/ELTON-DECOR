# Ozon: доказательства, границы и contract spike

Дата: 2026-10-06. Статус: **план проверки интеграции**, работающий checkout и доступ Elton Decor к API не подтверждены. ORD-04, ACC-03, RET-03 и продажа комплектов остаются условными/открытыми. Никакие credentials, реальные account IDs или договорные данные в документ не включены.

## 0. Этап 1: подготовка без провайдерских фактов

### Проверенный read-only boundary от 2026-10-07

ADR-014 разрешает узкий серверный пакет `packages/ozon` для ручного,
read-only чтения Seller API. Это **не** импорт, worker, HTTP route Elton API
или dependency гостевой корзины/заявки. Пакет принимает credentials только из
runtime configuration, использует фиксированный HTTPS origin
`https://api-seller.ozon.ru` и фиксированные Seller paths; браузер, OpenAPI
Elton и site price не получают ни credentials, ни provider payload.

Основание endpoint contract — датированный snapshot Seller OpenAPI из
`MissiaL/ozon-api` commit `9eec597cecafcdaa79d962f2363591ce19d90d86`,
проверенный 2026-10-07: declared source SHA-256
`822ed6f96499ab2f1865e714a97673da25d8f3f4ed29390194cf241891ccd112`.
Это evidence структуры request/response, не live entitlement, не доказательство
неизменности official contract и не разрешение на публикацию данных. Контрактные
fixtures синтетические и не содержат account/product/customer data. До отдельного
live smoke с разрешённым owner запуском отсутствуют claims о доступе Elton,
scopes, pagination semantics на account и rate-limit behaviour.

Первая реализация ограничена `POST /v3/product/list`,
`POST /v3/product/info/list`, `POST /v4/product/info/stocks` и
`POST /v2/review/list`; она возвращает typed provider observations/page cursors
только вызывающему server-side process. Reviews остаются disabled до Q-08;
stocks не становятся checkout availability; никакие observations автоматически
не записываются в PostgreSQL. Performance credential mapping не доказан и
Performance client/HTTP call не реализуются. Pay, Delivery, FBO posting/order,
reserve, callback, refund, return и любые mutations по-прежнему запрещены
BR-27/OZ-G1…6.

BA-SCOPE-01/BR-27 от 2026-10-06 утверждают локальную основу для демонстрации/начала подключения, не допуск Ozon. Трассировка: ORD-04/05, CAT-06, ADM-06/07, BR-02/10/14/15/17/18/24/25/27, S1-04/06. Версия документов/remote база — ARCHITECTURE §1. Нового live API evidence в этой документационной задаче не получено; исторические ссылки/индекс ниже не повышают статус доступа.

Первый путь storefront → Elton API → PostgreSQL сохраняет checkout_draft(state=saved), отдельный goods_total и snapshots. delivery.state=not_connected, delivery.amount=null, payable_total=null. Нет внешнего заказа, Seller posting, тарифа/ПВЗ/срока, FBO guarantee, payment/refund/ledger/purchase, настоящего SMS или customer profile. Сохранение BOM/base component prices не означает BR-15 net allocation, fulfillment или возможность partial refund.

Capabilities Pay/Delivery/Seller stock/real_checkout/reviews/SMS/refunds выключены на сервере; known disabled client command → CAPABILITY_DISABLED, unregistered provider callback →404. Ошибка не возвращает фиктивный external ID/paid/zero stock/free delivery. Bootstrap не создаёт Ozon client runtime и не требует provider secrets; если adapter boundary подготовлен, его unsupported result — явная ошибка, не mock success. QA доказывает zero outbound calls и absence provider/financial writes для прямых запросов к отключённым операциям. Только test double для этой отрицательной проверки не является интеграционной проверкой Ozon.

Для будущего подключения остаются interfaces/gates ниже. OZ-G1…6 блокируют коммерческий этап 2 и соответствующие capabilities, не каталог/корзину/локальную заявку. Saved drafts не отправляются автоматически после появления merchant key или смены flag. Требуется новая согласованная commercial command, fresh quote/availability/delivery, новое подтверждение пользователя и protected owner proof; контакт/телефон старой заявки не заменяет это. Такой migration/promotion flow пока не утверждён.

Пакет для начала onboarding: разрешённый synthetic demo магазина с видимыми ограничениями, список требуемых capabilities/вопросов и текущий evidence register. Список официально требуемых onboarding документов неизвестен и не придумывается; запросить через безопасный канал у провайдера в OZ-G1. Не отправлять PII/фото/ключи/финансовые payload в AI/design tools. Реальный sandbox/provider contract оформляются отдельной задачей после предоставления доступа.

## 1. Три разных уровня доказательства

### Официальная продуктовая страница — текущая проверка

На [официальной странице Ozon Pay + Delivery](https://finance.ozon.ru/business/acquiring/internet/dostavka) описаны продажи внешнего интернет-магазина с оплатой/доставкой, модели FBO и FBS, общие остатки одного товара для маркетплейса и сайта. Подключение связано с расчётным счётом Ozon Банка и подключением эквайринга; ограничения/допуск конкретного продавца следует проверить.

На [официальной странице интернет-эквайринга](https://finance.ozon.ru/business/acquiring/internet) описаны интеграция по API, возврат платежей через API и услуга онлайн-чеков. Эта информация подтверждает продуктовую возможность, но не параметры контракта и не обязанности конкретного магазина.

**Способ проверки 2026-10-06:** прямой web open обеих страниц вернул HTTP 403. Поиск вернул содержимое в индексе тех же официальных URL (даты обхода: примерно 2 и 3 месяца назад). Таким образом, повторно подтверждено содержание доступного индекса официальной страницы; это не прямое чтение API documentation и не доказательство неизменности условий сегодня. До реализации нужен актуальный официальный документ из подключения/кабинета. Маркетинговые цены/числа не приняты за договорные тарифы и KPI.

### Архив Seller API — историческая подсказка

В [SOURCES.md](SOURCES.md) зафиксирован разбор зеркала `stas711` со snapshot октября 2025. Ниже — **архивные пути, не подтверждённые текущие версии**. Это Seller API, а не автоматическое доказательство API внешнего checkout Pay/Delivery.

| Архивный путь/семейство | Что сказано в snapshot | Что нельзя вывести |
|---|---|---|
| `/v2/posting/fbo/list`, `/v2/posting/fbo/get` | Чтение FBO отправлений | Что можно создать FBO заказ внешнего сайта этими методами |
| `/v1/analytics/stocks` | FBO analytics stock, в архиве обновление раз в день в 07:00 UTC | Что API даёт real-time гарантированный FBO reserve/available сейчас |
| `/v4/product/info/stocks` | Остатки FBS/rFBS в этом snapshot | Что это актуальный FBO stock endpoint |
| `/v1/returns/list` | Seller return reading | Что метод создаёт возврат денег Pay или принимает внешнюю заявку |
| `/v1/review/list`, `/v1/review/info` | Доступ к отзывам связан с платной подпиской в архиве | Что Elton имеет entitlement и право републикации текста/фото |

Архив: [файл зеркала Seller API](https://github.com/stas711/ozon-seller-api-docs/blob/main/%D0%94%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D1%8F%20Ozon%20Seller%20API-3.MD). GitHub file blob SHA, проверенный 2026-10-06: `405e9372456999b1f13bdf1e91e1b8b223a28011`; это hash файла, не установленный commit всего snapshot. Полная provenance — [SOURCES.md](SOURCES.md). Зеркало не является официальным действующим контрактом. Эти пути не используются как готовый integration spec. Порядок страниц/cursors, schemas, rate limits и auth должны быть проверены заново.

### API contract / account entitlement — не проверены

Неизвестны действующие endpoints/версии Pay/Delivery; auth scopes; создание внешнего заказа; связь payment и fulfilment; quote/доставка/PVZ; provider reservation; подписи/семантика callback; query by idempotency key; отмена; частичный refund; комплекты; фискальные поля и права account. Архив Seller API эти пробелы не закрывает.

## 2. Границы адаптеров

`packages/ozon` — Python package, не npm. Предлагаются раздельные `SellerReadAdapter`, `PayAdapter`, `DeliveryAdapter` и опциональный `PerformanceReadAdapter` для marketplace advertising analytics, даже если часть продуктов объединена одним onboarding. Credentials/scopes и account mapping разделены. Frontend не обращается к Ozon API напрямую, кроме официально разрешённого hosted payment UI/SDK flow по документированному token.

Ниже — **наши Python interfaces**, не названия существующих методов Ozon:

| Interface | Предложенная семантика |
|---|---|
| `read_stock_snapshot(mapping, model)` | Normalized availability + as_of/fetched_at + source semantics; unknown не `{}`/0 |
| `read_fulfillments(cursor)` / `read_fulfillment(ref)` | Provider raw status + normalized state + external line IDs + timestamp |
| `quote_delivery(context)` | Доступные способы, цена, expiry, selection ref; только если контракт даёт |
| `begin_checkout(command, operation_key)` | Documented orchestration внешней покупки; не предполагать create Seller FBO |
| `read_payment(payment_ref)` | Подтверждённые amount/currency/state/merchant order reference |
| `request_cancel(order_ref, reason, operation_key)` | Допустимость и результат запроса, возможная отдельная компенсация платежа |
| `request_refund(payment_ref, allocations, operation_key)` | Partial/full refund с проверенной поддержкой lines/amount/receipt |
| `read_refund(ref)` | Проверенный financial result |
| `read_reviews(mapping, cursor)` | Optional; только entitlement + разрешение публикации |
| `submit_statistics_report(context)` / `read_report_status(ref)` / `fetch_report(ref)` | Optional PerformanceReadAdapter: async marketplace advertising report, schema/entitlement/endpoints не проверены; не checkout dependency |

Невозможный метод возвращает explicit `CapabilityUnsupported`, а не успех/mocked данные. Payload/endpoint mapping и normalized status table появляются только после official docs + sandbox verification. Domain services отвечают за суммы, ownership, snapshot и policy; adapter отвечает за внешний контракт, auth, pagination, normalization и error taxonomy.

## 3. Идентификаторы и каналы

Сохранять локальные product/order/item/payment/return/refund IDs отдельно от provider account, Seller offer/product/SKU, posting ID/number, Pay payment/refund ID, Delivery order/line ID и event ID. Совпадение строк/чисел не означает одинаковую сущность. Тип каждого ID/уникальность/scope/source/version фиксируется в mapping contract.

Каждая импортированная продажа имеет channel `ozon_marketplace`; внешний website order — `site`. Payment/refund/payout/fees также сохраняют channel и источник. Платежный callback не сопоставляется только по сумме или телефону. Сопоставление должно использовать проверенный merchant reference + external ID + currency/amount/account, с карантином неизвестных связей.

## 4. HTTP reliability и credentials

- HTTP connect/read/total deadlines, rate limit handling и bounded exponential backoff с jitter; значения из официального контракта/тестов, не придуманный SLA.
- Retry безопасного чтения при временных сетевых/5xx/429 ошибках; validation/auth/permission ошибки не «лечатся» бесконечным retry. `Retry-After` соблюдать, circuit breaker предложен для outage.
- Внешняя mutation при timeout → operation `unknown`. Повтор только при documented provider idempotency либо подтверждённом отсутствии первого эффекта. Stable local operation ID не доказывает provider idempotency.
- Payload redaction: без телефонов, адресов, secrets, карточных реквизитов и фото в логах/fixtures. Correlation local/external refs возможна без PII.
- Secrets в runtime secret store; Seller, Pay и Performance auth не приравниваются. Для подтверждённого Performance token flow — expiry, clock skew, singleflight refresh, scoped cache, renew on documented auth result. Сам flow/endpoints должны быть проверены; не считать, что Seller credential тоже такой token.
- Pagination/cursors, overlapping poll windows и provider watermark проверяются по contract. Poll не пропускает late updates; duplicates допустимы через inbox/unique fact.

## 5. Callback и сверка

Provider определяет HTTP route registration, schema, signature algorithm/headers, retry ack rules и event identity. Until verification подписанный payload/SDK нельзя выдумывать. Наш ingress ограничивает размер, проверяет raw-body signature по контракту и пишет durable inbox перед успешным receipt. IP restriction — дополнительный control.

Worker дедуплицирует транспортные события и business facts, проверяет current provider state при неоднозначности, сопоставляет account/channel/IDs/сумму/валюту. Применение state, ledger fact, inbox marker и outbox follow-up атомарно в PG. Return URL/browser event не подтверждает captured payment. Старый event не откатывает `succeeded`/`delivered`; неизвестные provider states сохраняются для mapping/reconciliation.

Periodic reconciliation: pending/unknown operations, missing callbacks, captured vs local total, refund totals, accepted-but-missing delivery, stuck fulfilments, stock age. Poll cadence и alerts согласовать по rate limits/latency. Платёж/доставка/товарный возврат/денежный refund — независимые факты; отмена заказа не приравнивается к refund.

## 6. FBO stock и reservation

Официальная продуктовая страница подтверждает общий остаток, но не атомарную бронь через Seller API. Локальная reservation решает гонку сайта в PG и **не бронирует Ozon stock**. Пока другой канал расходует общий запас, exact available на сайте нельзя гарантировать лишь local TTL.

Spike устанавливает значение available/free/reserved/on-hand каждого поля, его as_of, warehouse/model, частоту обновления и момент отражения website order. Если provider available уже за вычетом reserved, повторный subtraction запрещён. Локальный pending reserve учитывается лишь пока не отражён в provider availability по подтверждённой связи/watermark. При отсутствии доказуемого отражения выбирается согласованная conservative policy, а не формула «дважды вычесть для безопасности».

Архивный суточный FBO analytics snapshot подходит для исторического monitoring, но сам по себе не удовлетворяет checkout freshness. `/v4/product/info/stocks` нельзя назвать FBO решением на основе имеющегося FBS/rFBS snapshot. Новые покупки при stale/unknown stock регулируются Q-05; failure не превращается в stock=0.

## 7. Bundle, отмена и возврат

BR-14: flatten bundle в компоненты допустим только после доказательства, что внешний flow принимает нужные component IDs/qty и правильно осуществляет комплектацию, резерв, цену, delivery, cancel и partial refund. Независимая отгрузка нескольких коробок может требовать отдельного UX/сроков; единый комплект не предполагается автоматически.

BR-15 остаётся предложенным алгоритмом: после согласования server сохраняет детерминированные allocations в commercial order snapshot; суммы внешних строк/чека сверяются с локальным total. Если провайдер принимает только готовый Seller bundle SKU, требуется согласованный mapping/process. До gate неизвестное bundle fulfilment не маскируется обычным single SKU checkout.

Cancellation требует reason (ACC-03) и provider state guard. После confirmed cancel локальные reservations корректируются по stock contract; captured payment требует отдельного проверенного refund flow. Partial refund должен поддерживать сумму/позиции, уникальный operation key, повторный запрос, query и receipt, если применимо. Physical return state не вычисляется из Pay refund. Способ возврата товара и доставки, сроки и обязанности решаются Q-02/Q-07, не по догадке документа.

## 8. Contract spike gates

Каждый gate требует датированного отчёта: official docs/version/link, capability/account entitlement, обезличенные request/response fixtures, negative cases и выводы. Sandbox нужен реально предоставленный; локальный mock не закрывает gate. До результатов production endpoint contract отсутствует.

| Gate | Проверка | Условие pass / блокируемое поведение |
|---|---|---|
| OZ-G1 — продукт и доступ | Website merchant + Seller account + Pay/Delivery scopes; FBO; test access | Официальное подтверждение именно Elton flow; блокирует реальный checkout |
| OZ-G2 — IDs/quote/create | Product mappings, delivery selection/price, создать внешний order, сопоставить Pay/Delivery/Seller | Сохранённые IDs и согласованный порядок команд; запрещено угадывать create endpoint |
| OZ-G3 — payment/events | Captured/failed, signed callbacks, duplicate/out-of-order, потеря ответа, status query, idempotency window | Один charge/local fact, unknown корректно разрешается; блокирует платёжный запуск |
| OZ-G4 — stock/bundles | Available semantics/age, общий FBO stock, reservation reflection, конкурентный marketplace sale, bundle flow | Подтверждённая availability policy и component execution; блокирует гарантии stock/bundle продажу |
| OZ-G5 — cancel/refund/return | Причина отмены, cancel states, полный/частичный refund, потеря ответа, multiple refunds, physical return, чеки | Проверены financial/physical separation и bounded totals; блокирует автоматизацию возврата |
| OZ-G6 — review/operations | Отзывы entitlement/републикация; rate limits, token lifecycle, replay/reconcile, outage | Отзывы включаются отдельно; ops без потери фактов, принят runbook |

Если функция отсутствует или продавец не допущен, это не устраняется выдуманным adapter. Записать constraint и предложить решение заказчику: изменение процесса/провайдера/этапа выпуска. Нельзя молча включить Shopify как второй order authority или подменить Ozon иным payment checkout.

## 9. Reuse старого прототипа

`elton-dashboard-ai` (ревизия `cbe64fd3994c84971f5be617ace0bd662a4a79f7`) даёт идеи Seller polling и экономики маркетплейса; это не Pay/Delivery integration. Перед переносом нужны deadlines/retry taxonomy, token expiry where applicable, typed errors вместо `{}`, Decimal money, актуальные fixtures, configurable input costs/groups и channel isolation. Не переносить hardcoded бизнес-значения или unfinished calculations. Gemini относится к будущему AI V2 и не закрывает текущий contract spike.
