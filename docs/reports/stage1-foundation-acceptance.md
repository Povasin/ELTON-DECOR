# Stage 1 MVP acceptance evidence

Дата отчёта: 2026-10-07
Ветка: `feat/stage1-foundation`
Рабочая директория: `C:\Users\User\Desktop\E&D\stage1-foundation`

## Объём и требования

Проверен Task 8 плана `docs/superpowers/plans/2026-10-06-stage1-foundation.md`:

- `S1-01…S1-06`, `QA1`, `CAT-01…CAT-05`, `ORD-01…ORD-03`;
- `ADM-01`, `ADM-03`, `ADM-05`, `ADM-06`; локальный ADM-01 утверждён решением BA-AUTH-01/ADR-014;
- `BR-27` и инварианты API/БД: server-owned capabilities, guest ownership, immutable draft, no provider facts;
- CI без Ozon/Seller/Performance/Pay/Delivery/SMS секретов.

Источник требований: `PRODUCT.md`, `MVP_SCOPE.md`, `BUSINESS_RULES.md`, `ARCHITECTURE.md`, `DATABASE.md`, `API.md`, `OZON_INTEGRATION.md`, `SECURITY.md`, `QA.md`, `DEPLOYMENT.md`, `DECISIONS.md` и профиль `docs/agents/QA_DEVOPS.md` на базовом commit `91cbac2`.

## Реализовано

1. `apps/api/tests/test_disabled_capabilities.py` проверяет, что capabilities принадлежат серверу и все коммерческие флаги равны `false`; отложенные команды оплаты, доставки, SMS, refund, promotion и provider callback не зарегистрированы и заканчиваются `404 NOT_FOUND` до внешнего вызова или записи локального коммерческого факта.
2. `playwright.config.ts` и `tests/e2e/foundation.spec.ts` содержат сценарии storefront home/catalog/PDP/cart/checkout, same-origin proxy, guest ownership и admin session. Runtime E2E требует реальную PostgreSQL и явный флаг окружения.
3. `.github/workflows/foundation-checks.yml` запускает Python/PG, OpenAPI, frontend check/typecheck/proxy/build и условный Playwright. CI использует только синтетическую PostgreSQL строку; Ozon/provider credentials в job не передаются.

## Коммиты и миграции

Предыдущие принятые этапы:

| Этап | Коммиты |
| --- | --- |
| Bootstrap/schema/catalog/cart | `40512f3`, `767ee2f`, `f6eadc6`, `928df59`, `4287b6b`, `f83e0a8` |
| Local quote/immutable draft | `6d205d6`, `4eb602f` |
| Admin foundation | `c90b15d`, `86092cc`, `ac17790` |
| Media foundation and decoder gate | `ca0fdf3`, `7ba1ab6`, `c835a78`, `d6f2ae2` |
| Storefront/admin UI and proxy | `380455d`, `63d06c8`, `ad79198`, `91cbac2` |
| Task 8 QA/DevOps checks | `f79eca6`, `0dd53ac`, `4b710c4`, `907235a`, `d661947` |

Task 7 runtime fix `91cbac2` добавил корневые `html/body` в Next layouts; smoke-проверка выполнена после этого commit. Миграции `0001_catalog`, `0002_guest_drafts`, `0003_admin_access` остаются единственной системой PostgreSQL migrations через Alembic. Task 8 миграций не добавляет.

## Свежая проверка

| Команда | Результат |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest apps/api/tests/test_disabled_capabilities.py -q -rs --basetemp=.test-artifacts/pytest-task8-disabled` | `3 passed` |
| `.venv\Scripts\python.exe -m pytest -q -rs --basetemp=.test-artifacts/pytest-task8-full` | `109 passed, 55 skipped`; exit 0 |
| `.venv\Scripts\python.exe scripts/export_openapi.py --output .test-artifacts/task8-openapi.json` | exit 0 |
| `git diff --check` | exit 0 |
| `apps/api/tests/test_admin_access.py` + `test_admin_media.py` | `31 passed` (backend auth/media evidence from commit `5e9aefd`) |
| Protected admin catalog list/access tests | `24 passed` (commit `ee0df2b`) |
| `packages/ozon/tests` | `13 passed` (Seller read client, retry and secret-redaction evidence from commit `66ad420`) |
| Frontend Vitest / admin typecheck / OpenAPI check / admin build | passed in commit `9c33cdc` |
| `pnpm` from restricted sandbox | blocked by Windows `EPERM realpath`; direct frontend checks above were run before commit |

The full Python result is available without provider credentials. The 55 skips are the existing actual PostgreSQL gates; each reports missing `ELTON_TEST_DATABASE_URL`. No SQLite substitute or provider mock was used.

### Windows test harness note

A fresh restricted-run verification initially hung before the first FastAPI request in `asyncio.windows_events._make_self_pipe` while Starlette `TestClient` created AnyIO's ProactorEventLoop portal. The test suite now installs a Windows-only autouse `WindowsSelectorEventLoopPolicy` fixture in `apps/api/tests/conftest.py`. This changes only the test harness; production event-loop configuration is untouched. With the existing approved Windows loopback test execution, the focused and full commands above completed with `3 passed` and `109 passed, 55 skipped` respectively. A plain sandbox run remains unsuitable for loopback tests and is not counted as evidence.

Task 7 previously recorded successful frontend checks on commit `ad79198`. The closure frontend checks are recorded in commit `9c33cdc`; the current restricted shell cannot repeat pnpm workspace commands because Windows denies the sandbox realpath operation.

## Browser evidence

Targeted browser smoke observed the storefront response:

- `GET http://localhost:3000/` → `200`; storefront home rendered.
- `GET http://localhost:3001/login` is the intended admin entrypoint; the current restricted shell could not launch a fresh Next admin process because SWC cannot canonicalize the repository path without elevated Windows access.

The API was migrated and seeded against local PostgreSQL; `/health/ready` and `/api/v1/categories` returned 200 during the launch check. Full browser E2E still requires a shell with Windows loopback/realpath access and an installed Playwright browser. The CI job runs the suite only when `ELTON_E2E_ENABLED=1` and a runner plus runtime are provided.

## Open gates

- **PostgreSQL persistence/browser E2E:** run the remaining full persistence/concurrency and Playwright gates from a non-restricted Windows shell; no SQLite substitute is accepted.
- **ADM-01:** local one-owner login/session is implemented and approved by BA-AUTH-01/ADR-014. Customer SMS/OAuth/recovery remain out of Stage 1.
- **Media decoder:** raster images and MP4 video are decoded, metadata-stripped/re-encoded and published only as clean media; CAT-05/S1-01 video acceptance is verified locally with FFmpeg/ffprobe 9.0.2 and browser playback. Preview/production still requires the pinned runtime image/manifest from `docs/DEPLOYMENT.md`.
- **Ozon integration:** the Seller read-only client is server-only and fixture-tested. No live request, Performance token flow, review entitlement or Pay/Delivery operation was claimed.
- **Frontend local launch:** storefront and API were launched; a fresh admin Next process is blocked by the current sandbox’s Windows path permission and must be started from an elevated/non-restricted shell.

No deployment, cloud resource, external provider call, real customer/financial data, or secret was used by this task.
