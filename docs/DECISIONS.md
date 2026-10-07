# Журнал решений

Дата базовой подготовки: 2026-10-06. «Принято для документации» определяет устройство этого набора файлов; не означает production approval всей архитектуры.

| ADR | Решение | Статус | Основание / последствия |
|---|---|---|---|
| ADR-001 | Один monorepo и `/docs` как источник истины | принято для документации | явное указание заказчика; чаты не заменяют спецификацию |
| ADR-002 | Пять рабочих профилей; специализированные роли распределены | принято для документации | BA, Architect, Frontend, Backend/Ozon, QA/DevOps |
| ADR-003 | Next.js/TS витрина и admin; FastAPI/Python API | предложено | Python economics prototype полезен backend; два frontend приложения используют общую UI library |
| ADR-004 | PostgreSQL, SQLAlchemy/Alembic; Redis/Celery | предложено; обязательность Redis/Celery для bootstrap superseded by ADR-012/013 | PG/Alembic основа; Redis/Celery и коммерческие таблицы только при соответствующих задачах этапа 2 |
| ADR-005 | Guest checkout, SMS для покупателя; предложен отдельный admin email/password/server session | guest/SMS подтверждены; метод admin auth предложен | согласовать ADM-01 до реализации; менять customer flow на обязательную регистрацию/OAuth нельзя без BA change |
| ADR-006 | Seller API и внешний checkout — разные contracts | техническое ограничение | FBO posting list не доказывает создание заказов сайта; Pay/Delivery spike обязателен |
| ADR-007 | Нельзя считать локальную бронь бронью FBO | техническое ограничение | общие stocks изменяются вне сайта; provider authoritative availability/commit нужен |
| ADR-008 | Стек hosting и регион хранения | открыто | Vercel frontend и Supabase PG/Storage — кандидаты; production PII/data placement требует решения; Shopify — только альтернативная платформа |
| ADR-009 | elton-dashboard-ai — прототип для выборочного reuse | предложено | экономические формулы/репорты после сверки; не готовая админка, auth или core orders |
| ADR-010 | AI из Gemini cookbook вне MVP core | предложено | V2 помощник с tool permissions; без права самостоятельно платить/менять цены/возвращать деньги |
| ADR-011 | Bundles fulfillment, discount allocation и refunds | предложенный алгоритм; provider gate открыт | состав и правила в BUSINESS_RULES; транспорт/частичный refund подтверждаются контрактом |
| ADR-012 | Два этапа: локальная основа сейчас, реальная оплата/доставка позже | подтверждено заказчиком 2026-10-06 (BA-SCOPE-01) | BR-27/S1-01…06; supersedes прежнюю зависимость витрины/основы от полного коммерческого checkout; не подтверждает stack/auth/TTL/hosting/provider approval |
| ADR-013 | Отдельный immutable checkout_draft, server guest cart/owner proof, nullable delivery, минимальный PG bootstrap | проект Architect; Backend review до реализации | внутренние DB/API рекомендации этапа 1, не customer approval; finance/provider state не симулируются |
| ADR-014 | Локальное завершение этапа 1: owner admin auth, protected bootstrap, raster re-encode и проверенный read-only Ozon boundary | ADM-01 подтвержден заказчиком BA-AUTH-01 2026-10-07; technical contract проходит Backend review | Supersedes только pending admin-login gate ADR-005/013; BR-27 и этап 2 сохранены |

## ADR-014 — локальное завершение Stage 1

- **Дата/роль:** 2026-10-07, BA/Solution Architect. Версия входов: HEAD `0c8697a5102e6b9ff56e95889f319d8906f09d81`.
- **Evidence BA-AUTH-01:** заказчик выбрал прежний список оставшихся работ с пунктом «Согласовать ADM-01 для реализации admin login» и попросил «реализуй это чтобы получилось полноценное mvp этап 1 … на выходе запусти сайт». Это согласование уже предложенного admin метода и инструкция завершить локальную рабочую версию.
- **Customer decision:** один owner email/password/server session для local foundation_demo. Argon2id, hidden/runtime secret bootstrap/reset, random hashed sessions, rotation/revocation, exact Origin/CSRF и isolated guest/admin scopes — technical security contract. No default password/public signup. Production recovery/live PII/public release не утверждены.
- **Technical implementation:** использовать существующие Alembic 0001…0003; actual local PG, отдельный disposable test DB; catalog/cart/draft/admin/media browser flow. Raster uploads публикуются только после полного trusted decode и metadata-free derivative re-encode. Video требует отдельной доказанной pipeline.
- **Ozon boundary:** текущая команда разрешает отдельный read-only Seller/Performance adapter/CLI после docs/account verification, без provider calls в guest save и без смены site price provider price. Reviews остаются gated Q-08. Коммерческие Pay/Delivery/FBO order/SMS/refund/return и BR-27 gates сохранены.
- **Read-only evidence, 2026-10-07:** Backend/Ozon фиксирует Seller contract как community snapshot `MissiaL/ozon-api` commit `9eec597cecafcdaa79d962f2363591ce19d90d86`, declared Seller schema SHA-256 `822ed6f96499ab2f1865e714a97673da25d8f3f4ed29390194cf241891ccd112`. Это позволяет только contract-tested server client с fixed origin/paths и synthetic fixtures; live call, database import, storefront/API exposure и Performance token mapping не сделаны. Любой live smoke остаётся отдельным owner-authorized evidence task с redacted status/count output.
- **Контракты/review:** [closure specification](superpowers/plans/2026-10-07-stage1-closure.md), API/DATABASE/SECURITY; Backend проверяет их до реализации, QA фиксирует настоящие PG/E2E результаты. Исторические proposed решения не считаются production approval.

## ADR-012 — scope первого этапа

- **Дата/автор:** 2026-10-06, BA фиксирует явное решение заказчика, Architect отражает его технические последствия.
- **Контекст:** исходная база требовала commercial checkout до готовности MVP. Заказчик просит подготовить магазин для демонстрации/начала подключения Ozon, отложив реальную оплату и доставку.
- **Варианты:** ждать verified Pay/Delivery перед всей витриной; создать локальную основу первым этапом.
- **Решение/статус:** заказчиком выбран второй вариант, BA-SCOPE-01, PRODUCT/MVP_SCOPE/BUSINESS_RULES BR-27; исходные 25 IDs и BR-01…26 сохранены. Это утверждение scope, не endorsement конкретной реализации.
- **Последствия:** storefront/PDP/server guest cart/contact/address/local saved result/minimal protected admin сейчас; SMS/ЛК/оплата/статусы/возвраты/FBO/reviews после своих gates. Unknown delivery нельзя заменить 0; preview synthetic. Ozon gate не блокирует bootstrap, ADM-01/security всё ещё блокируют соответствующие зависимые функции.
- **Evidence/review:** явное решение заказчика от 2026-10-06 → BA FREEZE; Architect проверяет соответствие DB/API. Список обязательных документов Ozon/его одобрение этим решением не установлены.

## ADR-013 — технический дизайн foundation

- **Дата/автор:** 2026-10-06, Solution Architect. **Статус: proposed technical design, требуется Backend review перед implementation; customer approval не заявлен.**
- **Контекст:** BR-27 требует настоящие PG persistence/immutable snapshots/owner access/idempotency без внешних эффектов.
- **Варианты:** переиспользовать commercial orders с ложными payment/fulfillment defaults; отделить demo draft aggregate. Выбранная рекомендация — отдельные cart/draft_quote/checkout_draft и items/components, state только saved, no commercial table dependency. Полный customer schema и Redis/Celery откладываются.
- **Interfaces:** API first-stage inventory и exact DTO — API.md; migration groups/transaction — DATABASE.md. goods_total только товарная сумма; delivery.amount/payable_total null. Freeze BOM quantities/base prices без BR-15 refund allocation. Idempotency/quote consumption/immutable snapshots одним PG commit; replay before quote expiry. Будущий commercial promotion только отдельным согласованным fresh-confirmed command, без auto submission.
- **Trust:** persistent random HttpOnly guest cookie, PG token hash/owner/expiry; no ID/phone access. Same-origin Next proxy/local exact Origin+CSRF, отдельный server admin scope. ADM-01 остаётся proposed до approval, как ADR-005.
- **Technical demo recommendations:** session7 days/quote15 minutes, positive RUB siteprice, proposed contact/address DTO и media limits; фиксируются review/config/OpenAPI, не становятся утверждёнными retention/нулевыми ценами/provider правилами. File-only media validation/quarantine, no URL import SSRF. Hosting не выбран.
- **Consequences/review owner:** Backend/Ozon проверяет constraints/races/request hash; Frontend проверяет proxy/cookie/nullable totals/UI; QA проверяет actual PG/browser fail cases. План [stage1-foundation](superpowers/plans/2026-10-06-stage1-foundation.md) исполняется после review зависимых решений. Следующее документное изменение должно явно обновить ADR/DB/API, не молча принять policy.

## ADR-015 — варианты карточки товара вместо рекомендаций

- **Дата/автор:** 2026-10-07, решение заказчика зафиксировано Solution Architect.
- **Контекст:** форма админки называла связи товаров «Объединённые карточки» и описывала их как блок «С этим сочетается». Заказчик уточнил, что карточки должны объединять варианты одного товара, например разные цвета цветов, чтобы покупатель выбирал вариант как на Ozon. В новой форме создания также должен быть полный блок загрузки изображений и видео.
- **Варианты:** оставить рекомендации; ввести отдельный `variant_product_ids`; переиспользовать текущую relation-таблицу и wire-поле `related_product_ids`, изменив семантику и UI.
- **Решение/статус:** для foundation выбран третий вариант. Связи симметричны и обозначают варианты одной группы; storefront показывает их как «Выберите цвет или вариант». Имя `related_product_ids` временно сохраняется для совместимости с уже сгенерированным API-клиентом. Переименование поля выполняется отдельным согласованным изменением контракта.
- **Последствия:** рекомендации «С этим сочетается» не строятся из этих связей; у каждого варианта остаются отдельные SKU, цена, медиа и остаток. Админка использует одинаковую семантику при создании и редактировании. Новая карточка принимает изображения и один MP4 с прогрессом загрузки; первое изображение становится главным, видео занимает последнюю позицию.
- **Evidence/review owner:** явное уточнение заказчика от 2026-10-07; Backend/Ozon проверяет симметричную запись relations, Frontend проверяет выбор варианта и создание с медиа, QA проверяет реальный browser flow.

## ADR-016 — единое сохранение карточки и отложенная публикация медиа

- **Дата/автор:** 2026-10-07, решение заказчика зафиксировано Solution Architect.
- **Контекст:** отдельные кнопки сохранения и немедленные media mutations приводили к рассинхронизации layout: после сохранения карточки изображения и видео исчезали до ручного обновления страницы. Форма создания товара использовала иную разметку медиа, чем редактор.
- **Решение/статус:** и создание, и редактирование используют один общий media UX. Изображения, одно видео и удаления держатся в локальном черновике; пользователь подтверждает их единой кнопкой «Сохранить товар». Медиа отправляются только после успешного сохранения основных данных и получают окончательные позиции: изображения по порядку, видео после них. До начала операции витрина не получает черновое медиа; после подтверждения отдельной media-команды витрина получает только clean media.
- **Последствия:** API остаётся набором versioned commands, поэтому это не объявляется атомарной транзакцией. При ошибке после части команд админка перечитывает серверное состояние, не скрывает уже опубликованные медиа и сообщает о несохранённой части. Отдельные кнопки сохранения контента, цены, вариантов и медиа удаляются. Видео остаётся доступным только после успешного trusted pipeline из API.md.
- **Evidence/review owner:** явное уточнение заказчика от 2026-10-07; Frontend проверяет create/edit/staged-media и refresh-free layout, Backend/Ozon проверяет video pipeline и version conflicts, QA — browser flow и публикацию на витрине.

## ADR-017 — безопасная локальная телеметрия витрины

- **Дата/автор:** 2026-10-07, Solution Architect.
- **Контекст:** PRODUCT предусматривает события просмотра, поиска, корзины и checkout, а BR-25 запрещает раскрытие персональных и секретных данных в аналитике. Поставщик аналитики, consent и политика хранения не утверждены.
- **Решение:** витрина публикует небольшой allowlist событий в локальный `CustomEvent("elton:analytics")`, после строгой очистки полей. Сетевой провайдер, cookie, storage, персональные данные и клиентское `purchase` не добавляются.
- **Последствия:** UI может быть инструментирован и проверен без передачи данных третьей стороне. `purchase` возможен только из будущего серверного факта. Подключение внешнего получателя событий, retention, consent и серверная схема требуют отдельного ADR и product decision.
- **Evidence/review owner:** PRODUCT analytics, BR-25, tests/frontend/analytics.test.ts; Backend/Ozon владеет будущим серверным контрактом, Frontend — browser instrumentation.

## Открытые решения для основы

ADM-01 для локального этапа 1 согласован BA-AUTH-01/ADR-014; прежний approval blocker superseded, реализация и security evidence нужны для S1-05. Final CAT-03/Q-09/content, technical demo TTL/contact/address/positive-price/media recommendations требуют профильного review; это не требование provider API. Public preview/live PII требуют hosting/region/security/data release gate. BR-15, guest SMS claim, stale stock/резервы/refund policies — этап 2. Supabase/Vercel лишь hosting candidates; SupabaseAuth/Shopify second order authority не включаются.

## Как добавить ADR

Указать ID, дату, автора роли, контекст, варианты, выбранный вариант, влияние на требования/контракты, статус, evidence и owner review. Старые решения не удалять: отмечать `superseded by ADR-...`. Пока owner не назначен человеком, указывать роль, а не придумывать имя.

## Открытые решения до коммерческой оплаты этапа 2

1. Ozon Pay/Delivery entitlement продавца и живой контракт (external order, stock, callbacks, cancel, partial refund, fiscalization).
2. Возможность передачи bundle-компонентов и исполнения без самостоятельного bundle SKU.
3. Доступ/публикация Ozon отзывов и медиа.
4. Provider SMS, правила привязки гостевых заказов и recovery; лимиты/TTL после security review.
5. Фактический hosting, region, backup/restore и требования к персональным данным.
6. Операционная процедура возврата товара и денег, суммы/логистика/сроки; не выдавать предложения за правила заказчика.
