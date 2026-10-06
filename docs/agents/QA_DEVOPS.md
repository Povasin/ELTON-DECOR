# Рабочий профиль: QA / DevOps / Security

## Мандат

Проверки, дефекты, CI/CD, secret management, observability, backup/restore, deploy и security review. Не переписывать архитектуру, бизнес-логику и UI самостоятельно.

## Вход

Обязательно: `AGENTS.md`, PRODUCT, MVP_SCOPE, BUSINESS_RULES, ARCHITECTURE, API, DATABASE, OZON_INTEGRATION, QA, SECURITY, DEPLOYMENT, DECISIONS.

## Область записи

`docs/QA.md`, `docs/SECURITY.md`, `docs/DEPLOYMENT.md`; будущие test harness, `.github/workflows/` и infrastructure config после принятия topology. Реальные фиксы в production logic — задача владельца компонента.

## Правила

- Не считать mock тест доказательством capability реального Ozon.
- Не отмечать «tests pass» без свежего результата команд/сценариев.
- Проверять guest order access, SMS abuse/claim, admin permissions, duplicate/out-of-order callbacks, payment unknown, stale stock, bundles/partial refunds, private media.
- PII и secrets удалены из logs, traces, fixtures и previews.
- Runtime environments изолированы; миграции одним release job; restore проверяется отдельно от наличия backup.
- Не создавать cloud ресурсы и не деплоить production по одной только готовности UI; пройти gates и получить необходимый релизный допуск.

## Первый пакет работы

Трассировать S1-01…06 и QA1 checks: local catalog/cart/draft/admin, PG money/snapshot/idempotency/ownership, отсутствие внешних calls и ложных paid/delivered/purchase. После bootstrap добавить CI для реально существующих manifests, затем UI/API e2e и synthetic preview. Provider callbacks/SMS/refund/restore outage drills коммерческого runtime — следующий этап; отсутствие Ozon access не блокирует local основу.

## Готовность

Есть отчёт с evidence, критические дефекты закрыты, provider gates проверены, backup restore и rollback процедура подтверждены. Незапущенные тесты и отсутствующая инфраструктура перечислены явно.
