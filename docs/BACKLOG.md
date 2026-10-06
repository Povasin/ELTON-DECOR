# Очередь подготовки и MVP

Это задания для пяти профилей. Статус `planned` не означает выполненный код. Параллелить только задачи с утверждёнными входами и разными файлами.

| Задача | Владелец | Результат / критерий | Зависимость | Текущий статус |
|---|---|---|---|---|
| SETUP-01 | подготовка команды | дерево, /docs, profiles, rules, PR/issue templates | интервью | документационная база подготовлена; review до реализации |
| BA-01 | BA | согласовать открытые правила/суммы/возвраты/варианты, acceptance по IDs | PRODUCT/BR | planned |
| ARC-01 | Architect | принять стек, DB ownership, внутренние contracts, ADR и hosting region | BA-01 для зависимых правил | planned |
| OZ-01 | Backend/Ozon | live contract evidence: access, stock, external order, Pay, Delivery, callbacks, cancel/refund, bundle | полномочия продавца/договоры; OZON_INTEGRATION | requires external access |
| BOOT-01 | Backend/Ozon + Frontend по отдельным файлам | manifests, lockfiles, минимальный API/frontend без checkout; Alembic owner | ARC-01 | planned |
| FE-01 | Frontend | каталог/PDP/корзина, SEO, accessibility, синтетический preview | CAT-01…06, ORD-01, API; review дизайна | planned |
| BE-01 | Backend/Ozon | catalog/price/stock snapshot, cart/bundle service, admin data API | DATABASE/API/BR, BOOT-01 | planned |
| AUTH-01 | Backend/Ozon | guest capability, SMS sessions/claim, admin sessions, abuse controls | ACC-01…02, ORD-02, BR-04…08 | planned |
| ORD-01-IMPL | Backend/Ozon | order snapshot, idempotent checkout, payment/outbox/inbox/reconciliation | OZ-01, ORD-03…05, BR-10…18 | blocked by provider contract |
| FE-02 | Frontend | checkout и ЛК с pending/unknown/error состояниями | ORD-01-IMPL, AUTH-01 | planned |
| ADM-01-IMPL | Frontend + Backend/Ozon по отдельным задачам | admin товары/цены/bundles/заказы/возвраты; protected access | ADM-01…08, RET-01…03, API | planned |
| RET-01-IMPL | Backend/Ozon | return decisions, private photos, partial refund, provider reconciliation | BA-01, OZ-01; BR-19…23 | blocked by rules/contract |
| AN-01 | Backend/Ozon + Frontend instrumentation | schema событий, site vs marketplace, profit reconciliation | BR-25, contracts; prototype review | planned |
| QA-01 | QA/DevOps | contracts/integration/e2e с failures и money/access invariants | работающие components | planned |
| OPS-01 | QA/DevOps | CI, staging, logs/alerts/secrets, restore/rollback | принятый hosting ADR и manifests | planned |
| REL-01 | QA/DevOps + BA/Architect review | evidence QA/SECURITY/DEPLOYMENT, release допуска | QA-01, OPS-01, все критические gates | blocked |

## V2

Избранное, расширенные варианты/история цен по отдельному решению, дополнительные кабинеты/роли, loyalty/блог/OAuth и AI помощник — только после BA scope review. Gemini tools могут читать разрешённые данные/готовить предложения; core не зависит от модели. Новые service boundaries вводить по измеримой нагрузке, а не числу агентов.

## Перед началом реализации

Назначить реального исполнителя/ревьюера каждой задаче, документировать принятые ADR и предоставить доступ для integration spike безопасным runtime способом. Не вставлять merchant key в issue.
