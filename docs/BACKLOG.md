# Очередь подготовки и MVP

Это задания для пяти профилей. По BA-SCOPE-01 от 2026-10-06 сначала готовится основа магазина для демонстрации/подключения Ozon, затем коммерческие интеграции. Границы — [MVP_SCOPE.md](MVP_SCOPE.md), BR-27. Статус `planned` не означает выполненный код. Параллелить только задачи с согласованными входами и разными файлами.

## Этап 1 — основа магазина

План конкретных файлов, интерфейсов и проверок: [stage1-foundation](superpowers/plans/2026-10-06-stage1-foundation.md). План ещё не выполнен; согласование предложенных методов/параметров не подменяется фактом его написания.

| Задача | Владелец | Результат / критерий | Зависимость | Текущий статус |
|---|---|---|---|---|
| SETUP-01 | подготовка команды | дерево, /docs, profiles, rules, PR/issue templates | интервью | документационная база подготовлена; review до реализации |
| BA-01 | BA | обновить два этапа, BR-27, критерии S1-01…06; сохранить исходные требования | явное решение заказчика | документы подготовлены; открытые правила сохраняются |
| ARC-01 | Architect | уточнить stage1 DB/API, disabled capabilities и план основы приложений | BA-01 | документационный проект; readiness решений в DECISIONS |
| BOOT-01 | Backend/Ozon + Frontend по отдельным файлам | manifests/lockfiles, API/PG и два frontend; Alembic owner, синтетическое наполнение | ARC-01, план foundation | planned; Ozon credentials не требуются |
| FE-01 | Frontend | главная/catalog/PDP/cart, SEO, accessibility; затем подключение к Elton API | CAT-01…05, ORD-01, API; review дизайна | planned |
| BE-01 | Backend/Ozon | catalog/price/bundle content, сохраняемая guest cart, серверный расчёт | DATABASE/API/BR, BOOT-01 | planned; FBO availability неизвестна, sync выключен |
| ADMIN-AUTH-01 | Backend/Ozon | отдельный protected admin; guest proof и ownership локальных заявок | BR-05/07, ADM-01, stage1 API; метод ADM-01 согласовать до реализации | planned |
| DRAFT-01 | Backend/Ozon | локальная заявка со снимком и идемпотентностью; никаких payment/fulfillment/provider facts | ORD-02/03, BR-03/18/27; guest access | planned |
| FE-DRAFT-01 | Frontend | форма синтетических контактов/адреса и результат «оплата и доставка не подключены» | DRAFT-01, API | planned |
| ADM-BASE-01 | Frontend + Backend/Ozon по отдельным задачам | admin товары/медиа/цены/составы и просмотр заявок; без ручных paid/delivered статусов | ADM-01/03/05/06, stage1 API | planned |
| QA-BASE-01 | QA/DevOps | QA1 checks, PG concurrency/idempotency/ownership, UI/API integration | работающие stage1 компоненты | planned; mocks не закрывают S1-06 |
| OPS-BASE-01 | QA/DevOps | воспроизводимый local запуск, CI для существующих manifests; план synthetic preview | BOOT-01, выбранные runtime конфигурации | planned; облака не созданы |
| DEMO-01 | QA/DevOps + BA/Architect review | S1-01…06, отсутствие внешних side effects, protected demo/admin | stage1 задачи; QA/SECURITY/DEPLOYMENT | planned; готовность и одобрение Ozon не заявлены |

## Этап 2 — коммерческая версия

Следующие задачи не являются зависимостью BOOT-01/BE-01/DRAFT-01. Они остаются обязательными перед включением соответствующего реального поведения.

| Задача | Владелец | Результат / критерий | Зависимость | Текущий статус |
|---|---|---|---|---|
| OZ-01 | Backend/Ozon | live contract evidence: доступ/stock/external order/Pay/Delivery/callbacks/cancel/refund/bundle | подготовленная демонстрация; реальные требования onboarding и доступ Ozon | deferred; requires external access |
| BA-COM-01 | BA | согласовать политики stock/bundles/возвратов/доставки/guest account claim | PRODUCT Q-01…Q-11 и результаты spike | deferred |
| AUTH-01 | Backend/Ozon | SMS/ЛК/claim и abuse controls без подмены customer auth | ACC-01…02, ORD-02, BR-04…08; SMS provider | deferred |
| ORD-01-IMPL | Backend/Ozon | реальный checkout/payment/outbox/inbox/reconciliation; новая проверка условий вместо автоматического исполнения demo заявки | OZ-01, BA-COM-01; ORD-03…05, BR-10…18/27 | blocked by provider contract |
| FE-02 | Frontend | реальный checkout и ЛК, независимые pending/unknown/error статусы | ORD-01-IMPL, AUTH-01 | deferred |
| ADM-01-IMPL | Frontend + Backend/Ozon по отдельным задачам | расширенные provider заказы/статусы/остатки и возвраты | ADM-02…08, RET-01…03, API | deferred |
| RET-01-IMPL | Backend/Ozon | return decision/private photos/partial refund/provider reconciliation | BA-COM-01, OZ-01; BR-19…23 | blocked by rules/contract |
| AN-01 | Backend/Ozon + Frontend instrumentation | verified purchase/refund и раздельные site/marketplace метрики | BR-25, финансовые факты/согласованные определения | deferred; stage1 draft не является purchase |
| QA-01 / OPS-01 | QA/DevOps | provider integration/e2e, staging, restore, мониторинг unknown | работающие коммерческие компоненты и закрытые gates | deferred |
| REL-01 | QA/DevOps + BA/Architect review | G-01…10 и QA commercial gates, реальная готовность выпуска | все критические условия коммерческого этапа | blocked |

## V2

Избранное, расширенные варианты/история цен по отдельному решению, дополнительные кабинеты/роли, loyalty/блог/OAuth и AI помощник — только после BA scope review. Gemini tools могут читать разрешённые данные/готовить предложения; core не зависит от модели. Новые service boundaries вводить по измеримой нагрузке, а не числу агентов.

## Перед началом реализации

Назначить реального исполнителя/ревьюера каждой задаче и зафиксировать используемую версию DB/API/ADR. Для этапа 1 не нужны merchant credentials. Доступ для integration spike понадобится на этапе 2 и передаётся безопасным runtime способом; не вставлять merchant key в issue.
