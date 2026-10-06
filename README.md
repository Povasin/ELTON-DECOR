# Elton Decor

Единый репозиторий интернет-магазина и админки. Источник истины — [`docs/`](docs/PRODUCT.md). Подготовлено 2026-10-06 по BA-интервью и исследованию Ozon / Elton Dashboard / Gemini.

**Состояние:** документация, инструкции пяти агентов и структура репозитория. Production-приложения, схема в работающей БД, CI и облачные ресурсы ещё не созданы. Рекомендуемый стек является предложением; критические Ozon-контракты требуют проверки.

## С чего начать

1. [`PRODUCT.md`](docs/PRODUCT.md) — требования и сценарии заказчика.
2. [`MVP_SCOPE.md`](docs/MVP_SCOPE.md) и [`BUSINESS_RULES.md`](docs/BUSINESS_RULES.md) — границы MVP и единые правила.
3. [`ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`DATABASE.md`](docs/DATABASE.md), [`API.md`](docs/API.md) — целевая архитектура и проект контрактов.
4. [`OZON_INTEGRATION.md`](docs/OZON_INTEGRATION.md) — подтверждения, ограничения, spike до реализации checkout.
5. [`AGENT_ROLES.md`](docs/AGENT_ROLES.md), [`WORKFLOW.md`](docs/WORKFLOW.md), [`BACKLOG.md`](docs/BACKLOG.md) — кто работает и в какой последовательности.
6. [`QA.md`](docs/QA.md), [`SECURITY.md`](docs/SECURITY.md), [`DEPLOYMENT.md`](docs/DEPLOYMENT.md) — проверки и выпуск.
7. [`DECISIONS.md`](docs/DECISIONS.md), [`SOURCES.md`](docs/SOURCES.md), [`PLUGINS.md`](docs/PLUGINS.md) — решения, доказательства, инструменты.

## Структура

```text
elton-decor/
├── AGENTS.md
├── apps/
│   ├── storefront/       # Next.js / TypeScript — витрина, SEO, кабинет
│   ├── admin/            # Next.js / TypeScript — админка
│   └── api/              # FastAPI — core API и worker entry points
├── packages/
│   ├── ui/               # общие React компоненты и дизайн токены
│   ├── database/         # Python модели, Alembic migrations
│   ├── ozon/             # Python adapters Seller / Performance / Pay / Delivery
│   └── analytics/        # event schemas и расчёты с разделением каналов
├── docs/
│   ├── agents/           # пять рабочих профилей
│   └── ...               # требования, контракты, gates
└── .github/              # шаблоны задач и PR
```

Папки содержат описание ответственности, а не готовые приложения. Python-пакеты не становятся npm-пакетами из-за расположения в `packages/`. Рабочий tooling и lockfiles появятся при реализации после выбора версий и принятия ADR. Одна БД, один владелец миграций — Alembic.

## Рабочие профили

| Профиль | Основная область |
|---|---|
| [BA](docs/agents/BA.md) | требования, scope, правила, критерии приёмки |
| [Architect](docs/agents/ARCHITECT.md) | архитектура, DB/API, ADR, интеграционные контракты |
| [Frontend](docs/agents/FRONTEND.md) | storefront/admin UI, SEO, клиентские события |
| [Backend/Ozon](docs/agents/BACKEND_OZON.md) | core API, auth, заказы, adapters, worker, аналитика |
| [QA/DevOps](docs/agents/QA_DEVOPS.md) | проверки, CI, безопасность, эксплуатация |

Перед началом любой работы прочитай [`AGENTS.md`](AGENTS.md). Специализированные роли Admin/Analytics, SEO, Ozon Integration и Security распределены между этими пятью профилями.

## Следующий шаг

Проверить Ozon Pay/Delivery для конкретного продавца и согласовать открытые бизнес-правила. До этого можно реализовать каталог, дизайн прототипы и UI по стабильным mocked contracts. Нельзя обещать работающую покупку с общих FBO-остатков без подтверждённого provider contract.
