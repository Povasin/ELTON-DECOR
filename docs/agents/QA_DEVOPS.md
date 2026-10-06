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

Трассировать acceptance requirements → checks; проверить docs/contracts. После bootstrap добавить CI для реально существующих manifests, а затем integration/e2e. Подготовить выбранный runtime и провести restore/callback outage drill в staging.

## Готовность

Есть отчёт с evidence, критические дефекты закрыты, provider gates проверены, backup restore и rollback процедура подтверждены. Незапущенные тесты и отсутствующая инфраструктура перечислены явно.
