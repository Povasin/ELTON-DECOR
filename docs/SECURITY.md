# Безопасность и границы доверия

## Активное дополнение 2026-10-07 — локальный этап 1

BA-AUTH-01/ADR-014 утверждают one-owner email/password/Argon2id/server-session ADM-01 только локально. Исторический pending approval ниже superseded для этого сценария. Bootstrap/reset — CLI в explicit foundation_demo с loopback PostgreSQL: email/runtime input, пароль hidden prompt либо локальный ignored secret file с ограниченными правами; пароль не CLI argument, source, seed, stdout или log. Bootstrap под PG lock отвергает второй owner, создаёт hash/permissions/audit атомарно; reset того же owner отзывает все sessions. Автоматически созданный пароль хранится только в локальном защищённом runtime secret store, пользователю сообщается путь, не значение.

Login/session/logout obey API.md: exact Origin, bounded IP/account limits, generic credential failure/dummy hash verification, random hashed token, rotation/revocation/expiry, isolated guest/admin scopes и session-bound CSRF. Cookie HttpOnly/SameSite, Secure=false только loopback HTTP. Новые пароли bootstrap/reset не короче 12 символов и не длиннее 128; пароль не нормализуется. Это technical local security policy, не production recovery approval.

Товарные изображения проходят full trusted decode, bounded bytes/dimensions/pixels, EXIF transpose и fresh raster re-encode без metadata; публичны только проверенные derivatives по server UUID key, после durable storage + clean DB/audit. Corrupt/spoofed/animated/bomb/SVG/HTML content отвергается. Проверка signature без decode недостаточна. Видео disabled до отдельной проверенной pipeline. Read-only Ozon credentials используются только server runtime в explicit adapter/CLI, verified operation allowlist, без customer/posting/return payloads и без сырого payload в logs/fixtures. Review publication остаётся закрытой до Q-08. Все BR-27/live PII/production gates сохранены.

Статус: **предложенная модель защиты**, 2026-10-06. Приложение, инфраструктура и проверки безопасности не реализованы. Это требования к будущей реализации/проверке, а не заявление о защищённости. Размещение данных, правовая оценка, retention и эксплуатационные роли открыты.

## Применимость первого этапа

Первый этап по [MVP_SCOPE.md](MVP_SCOPE.md) сохраняет локальную демонстрационную заявку и не принимает платежи/не создаёт доставку. Он не требует merchant credentials, SMS integration или открытого доступа к реальным покупательским данным. Guest ownership, admin permissions, CSRF, безопасные загрузки товарных медиа и redaction применяются уже к этому этапу. Нельзя считать отключённую оплату причиной отключить защиту контактов/адресов в тестовом сценарии.

Платёжные/callback/refund/return-photo меры ниже предназначены для последующей активации соответствующих функций. До согласования хранения данных и live release демоверсия использует синтетические данные; ручной приём оплаты/исполнение заявок отдельным бизнес-процессом не согласованы.

## Активы и границы доверия

Активы: PII покупателя/адрес, принадлежность заказа, SMS-коды/сессии, admin credentials, provider secrets, снимки заказа/ledger, остатки/резервы, private return media, backups и аудит.

| Граница | Недоверенные входы | Серверная проверка |
| --- | --- | --- |
| Browser → frontend/admin → API | Цена/скидка/SKU/quantity/role/user/order ID | Schema/limits, права/ownership, актуальные правила; immutable order snapshot |
| Guest/SMS → аккаунт/заказы | Телефон и знание номера заказа | SMS и согласованное правило ownership; знание ID/телефона не открывает архив |
| Admin browser → API | Мутации/cookie/чужой origin | Admin server session, полномочия, CSRF, аудит |
| Провайдер → callback | Подпись/event ID/status/time/amount/currency/внешняя связь | Подлинность по проверенному контракту, связь/channel, допустимый переход, inbox/domain idempotence |
| API/worker → провайдер | Ответ/timeout/rate limit/доступность функции | Контракт/entitlement, retry taxonomy и сверка unknown; отсутствие ответа не доказывает отказ |
| API/worker → PostgreSQL/Redis | Повторы/конкурентность/потеря worker или Redis | DB constraints/transactions, atomic inbox/outbox; ledger не только в Redis |
| Пользователь → private storage | File name/MIME/content/metadata/size/key | Ownership обращения, фактический тип/размер, server key/private ACL; доступ после авторизации |
| CI/preview → runtime/secrets | PR/зависимости/build output/logs | Изоляция/minimum permissions; fork PR и browser build не получают секреты |

Admin не может обойти правило провайдерских fulfillment statuses. Локальный резерв не гарантирует общий FBO-резерв Ozon. Shopify как возможная поздняя альтернатива требует решения об authority, не вводится вторым владельцем заказов.

## Покупатель, guest и admin

Подтверждены гостевая корзина/оформление и SMS-вход покупателя. Отдельный вход администратора по email/password с серверной сессией — единый предложенный контракт ADM-01, который требует согласования. Изоляция покупательских и административных полномочий, отсутствие паролей/секретов в исходниках — инженерные инварианты. OAuth/обязательная регистрация вне текущего scope. Кандидат Supabase PostgreSQL/Storage не заменяет эти механизмы автоматически.

Предложенные меры:

- SMS-код кратковременный, одноразовый, с серверными лимитами выдачи/перебора; параметры после выбора провайдера. Код не логируется; ответы не раскрывают существование аккаунтов/заказов.
- Guest order привязывается после проверки владения по принятому правилу. Совпадение текущего телефона не даёт весь архив: нужно учитывать смену/перевыпуск номера. Смена телефона/recovery пока не определены.
- Guest-доступ к конкретному заказу требует согласованной server session либо ограниченного секретного resource token. Публичный ID/телефон/UUID не являются доказательством права. Токены не попадают в logs/analytics/referrer.
- Пароль администратора хранится как стойкий хеш по выбранной политике; первичная выдача/восстановление доступа — защищённый процесс без стандартного пароля. MFA относится к возможному развитию после MVP по решению заказчика.
- Server sessions имеют срок, ротацию при входе/смене прав, отзыв и logout. Cookie Secure/HttpOnly и подходящий SameSite; конкретный CORS и CSRF для cookie mutations по фактическому размещению.
- Каждый запрос проверяет роль/ownership; покупатель не получает admin scope. DB/storage/worker/service accounts получают минимум прав. Browser не получает service-role/provider secrets.

Точные session/SMS/MFA параметры и эксплуатационные роли не утверждены. Один admin не отменяет аудит/контроль сессий.

## Деньги и внешние события

Order/payment/refund — отдельные state machines, внешние ID/channel и переходы проверены по контракту. Деньги — minor units/Decimal с явной валютой/округлением. Цена, состав и allocation скидки bundle фиксируются в заказе; клиентская сумма/текущая цена не управляют refund.

Idempotence требует уникальных ключей/ограничений PostgreSQL, проверки конфликтующего payload и domain invariants. Inbox отсекает callback duplicates; ledger и максимальная сумма возврата защищают даже при разных event ID. Outbox и изменение состояния атомарны. Порядок доставки не равен порядку бизнес-событий.

Callback signature algorithm/header, key rotation, replay window и status verification method — **неизвестные свойства API** до contract spike. Не придумывать endpoint/header и не считать IP allowlist достаточной аутентификацией. Непроверенный callback не создаёт paid/refunded. Подлинное событие с неизвестной связью не связывается по совпадению телефона/суммы.

Timeout после возможного внешнего эффекта создаёт unknown/reconciliation. Внешний retry — по доказанной idempotence либо после сверки. Финансовый статус не «исправляется» ручной сменой fulfillment.

## Фото возвратов и PII

Фото — private storage. API выдаёт кратковременную ссылку после проверки права на обращение; public bucket/постоянная ссылка недопустимы. Ключ объекта выбирает сервер; имя файла не становится путём. Проверяются фактический тип/размер/число файлов, исключается выполнение HTML/SVG/scripts как активного контента. По предложенной архитектуре файл проходит карантин и проверку до показа. Форматы, параметры проверки/обработки и очистка EXIF — решения до включения загрузок.

Подписанная ссылка доступна любому обладателю до expiry: ограничить TTL, исключить logs/analytics, проверить cache policy. Срочный отзыв/удаление выбирается со storage. Выдача аудируется без token; admin-доступ требует admin session.

Минимизировать PII: один адрес профиля и необходимый immutable address snapshot заказа. Определить цели/retention/удаление отдельно для профиля, заказов/финансовых записей, media, аудита/backups/logs. Не обещать мгновенное удаление обязательных записей без политики. Нужны процедуры доступа/удаления и учёт данных у внешнего провайдера.

Регион/поставщики SMS/payment/delivery, доступ поддержки, копии и трансграничные потоки не согласованы. До production требуется решение о допустимом размещении/обязательствах. Документ не утверждает соответствие законодательству и не заменяет оценку.

## Секреты, журналы и analytics

- Secrets — управляемое runtime-хранилище по роли/окружению; механизм не выбран. В исходниках, документах, `NEXT_PUBLIC_*`, images/artifacts и примерах нет значений.
- Local/staging/production credentials и DB/storage roles разделены. Rotation/revocation и процедура утечки требуют утверждения.
- Не логировать Authorization/cookie/SMS/password/token, реквизиты, полный телефон/адрес, media/signed URL и raw payload. Фильтрация до logging/tracing/error reporting; redaction тестируется на ошибках/retry.
- Логи содержат technical IDs/channel/event/transition/error/correlation ID. Аудит admin: actor ID/action/resource/time/result, без копирования PII; доступ ограничен.
- Analytics: согласованная schema/allowlist, запрет PII/secrets также для SDK. Retention/access/delete logs и analytics открыты.

## Предлагаемые меры платформы

TLS на публичных границах и защита внутренних каналов; DB/Redis без публичного общего доступа; private storage; шифрование данных/backups и разделение ключей. Frontend требует согласованные CSP/security headers/внешние scripts; API — schema/length limits, rate limits, контролируемые outbound endpoints и доверие forwarded headers. Сетевые конфигурации пока не созданы.

Зависимости: reproducible lockfiles, review обновлений, будущие scans, minimum permissions Actions и branch protection. Findings имеют фиксированное решение; раскрытый секрет отзывается, а не только удаляется из последней версии файла.

## Проверка и инциденты

До production должны пройти ownership order/media, admin role bypass, SMS/session/CSRF, callback authenticity/replay, financial idempotence и log redaction из [QA.md](QA.md). Изменения auth/callback/storage/money требуют review по этим случаям. Отчёты отсутствуют.

Предложенная реакция: ограничить затронутые операции/доступ; отозвать secrets/sessions; сохранить защищённые доказательства без расширения утечки; определить затронутые данные/деньги; сверить провайдера; устранить причину/проверить восстановление; выполнить необходимые уведомления по утверждённому процессу. Контакты/полномочия/сроки/каналы пока не назначены; ответственные не выдумываются.

К выпуску нужны решения по region/retention, guest ownership/смене телефона, auth, callback contract, private media, secrets и инцидентам. Все cloud-ресурсы **unprovisioned**; Vercel/Supabase — кандидаты из [DEPLOYMENT.md](DEPLOYMENT.md).
