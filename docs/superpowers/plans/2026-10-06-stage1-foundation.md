# Stage 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать работающую локальную основу магазина с каталогом/PDP, серверной гостевой корзиной, неизменяемой заявкой и защищённой минимальной админкой на синтетических данных.

**Architecture:** Storefront и admin — отдельные Next.js интерфейсы единого FastAPI API с PostgreSQL. Alembic в packages/database владеет схемой; guest session, cart, quote, draft и idempotency сохраняются сервером. Операции Ozon/SMS/оплаты/доставки отключены, товарные медиа проверяются локальным обработчиком файлов.

**Tech Stack:** Рекомендации ADR-003/013: TypeScript/Next.js, Python/FastAPI/Pydantic/SQLAlchemy/Alembic, PostgreSQL, pnpm и uv, pytest/Playwright; FFmpeg/ffprobe для безопасного MP4 пути. Совместимые поддерживаемые версии выбираются и фиксируются при bootstrap review; здесь нет выдуманных точных versions.

**Spec:** [PRODUCT](../../PRODUCT.md), [MVP_SCOPE](../../MVP_SCOPE.md), [BUSINESS_RULES](../../BUSINESS_RULES.md), [ARCHITECTURE](../../ARCHITECTURE.md), [DATABASE](../../DATABASE.md), [API](../../API.md), [OZON_INTEGRATION](../../OZON_INTEGRATION.md), [DECISIONS](../../DECISIONS.md), [SECURITY](../../SECURITY.md), [QA](../../QA.md), [DEPLOYMENT](../../DEPLOYMENT.md). BA-SCOPE-01; CAT-01…05, ORD-01…03, ADM-01/03/05/06; BR-03/04/05/06/07/09/12/17/18/27; S1-01…06.

## Global Constraints

- «Деньги считаются в minor units либо Decimal, без float» (BR-03); API Money.amount_minor — integer string, RUB.
- «Неподтвержденная стоимость доставки не подменяется бесплатным тарифом» (BR-27); delivery.amount=null и payable_total=null, goods_total отдельно.
- «Сохранение не вызывает Ozon Pay/Delivery/FBO или реальные SMS, не создает аккаунт автоматически, не ставит оплату/доставку/исполнение и не порождает purchase» (BR-27).
- «Гость имеет доступ только к своему локальному результату; ID/телефон сами по себе не подтверждают право доступа» (BR-27).
- «ADM-01 остается предложенным контрактом и согласуется до реализации входа» (BR-27).
- «Preview и демонстрация используют синтетические данные» (BR-27); production/cloud provisioning/реальные PII не входят в план.
- packages/database — единственный SQLAlchemy/Alembic owner; no Prisma/Supabase migrations/Auth/Shopify order authority.
- saved draft неизменяем, BOM/base prices заморожены, BR-15 net allocations/refund policy не реализуются как принятые.
- same-origin /api/v1 proxy; localhost:3000 storefront, localhost:3001 admin, API127.0.0.1:8000; exact Origin + CSRF, разные server scopes.
- demo session7 days/quote15 minutes и media limits — предлагаемые технические настройки ADR-013, проходят review, не production retention.

## Review Focus

- Одновременная admin смена цены/BOM при сохранении: один согласованный снимок или QUOTE_CHANGED; тест Task 4.
- Потерянный успешный ответ, затем истечение quote: тот же key/body возвращает тот же draft; тест Task 4.
- Закрытый браузер/другой localhost порт: persistent cookie работает, guest scope не открывает admin/чужой ID; tests Tasks3/7/8.
- Удалённый/неактивный или неоценённый компонент в существующей корзине: видимый issue и отказ quote, без выдуманной суммы; tests Tasks3/4.
- Поддельный MIME/опасный файл/невалидный MP4: проверка до публикации; без clean media pointer и без URL fetch; test Task 6.

---

## Состояние, порядок и владельцы

Документная база remote142c0a1186a48994b26048c06182c0ea1757049d + BA FREEZE2026-10-06; document branch docs/stage1-ozon-onboarding. Все filenames/commands ниже **будущие**: scripts/manifests/tests пока отсутствуют. Перед исполнением создать implementation feature branch по WORKFLOW. Каждый commit включает ссылку на IDs/ADR и только свою область; open user changes не включать.

Выполнять Task 1→2→3→4→5→6→7→8. ADM-01 задерживает auth-часть Task 5 и полную приёмку admin, не остальные подготовительные задачи. Корневые pyproject.toml/uv.lock/compose.local.yaml/.gitignore и Python workspace принадлежат Backend (Task 1). Корневые package.json/pnpm-workspace.yaml/pnpm-lock.yaml и TS workspace принадлежат Frontend (Task 7). Shared API source contract принадлежит Backend с Architect review; Frontend владеет apps/storefront/apps/admin/packages/ui/packages/api-client, сгенерированные types обновляет по frozen OpenAPI. QA пишет tests/e2e и .github/workflows в Task 8. Параллельную запись в общий main/config/contracts не планировать. После фиксации активного API/DTO Task 7 scaffold/proxy/UI types могут готовиться в своей области одновременно с Backend Tasks 3–6; каталог/cart интегрируются после Task 3, заявка после Task 4, admin после Task 5, media после Task 6. Это не закрывает E2E до actual backend. Изменение shared contract сначала freeze/review, затем regeneration, без одновременных правок одного файла.

Предложенная структура Python: apps/api/src/elton_api и packages/database/src/elton_database; доменные services в API, SQLAlchemy models/repositories в database. Frontend app router paths ниже, общий API client генерируется из OpenAPI активного этапа. Workspaces не являются отдельными источниками заказов.

### Task 1: Воспроизводимый local API/PG bootstrap

**Owner:** Backend/Ozon; Architect review stack/tooling. **Зависимость:** документный review ADR-013.
**Files:** Create pyproject.toml, uv.lock, compose.local.yaml, .gitignore, apps/api/pyproject.toml, apps/api/src/elton_api/main.py, config.py, capabilities.py, packages/database/pyproject.toml, packages/database/src/elton_database/session.py, apps/api/tests/conftest.py, apps/api/tests/test_bootstrap.py, scripts/export_openapi.py; Modify README.md только после проверки текущей пользовательской правки/отдельного согласования содержимого.
**Interfaces:** get_session() → Iterator[Session]; Settings(mode=foundation_demo,database_url,guest_origins,admin_origins,session_csrf_key); create_app(settings:Settings) → FastAPI. GET /health/live →{status:"ok"}, GET /health/ready проверяет PG; active CapabilitiesDTO по API.md. Root compose сервис только pg, API запускается uv; no Redis/SMS/Ozon dependency.

- [ ] Зафиксировать поддерживаемые совместимые версии в manifests/lockfile по официальным источникам; настроить local PG/test DB и runtime secret injection без значений в tracked files.
- [ ] Написать test_bootstrap.py::test_ready_requires_pg и ::test_foundation_has_no_provider_dependency: реальное подключение PG, unavailable PG→503, no Ozon/SMS credentials required.
- [ ] Запустить `uv run pytest apps/api/tests/test_bootstrap.py -q`; ожидается FAIL до реализации.
- [ ] Реализовать указанные интерфейсы, health/capabilities и экспорт только stage1 OpenAPI; configured origins/CSRF secret обязательны.
- [ ] Запустить предыдущие tests и `uv run python scripts/export_openapi.py --output .test-artifacts/openapi.json`; ожидается PASS/валидная schema без активных payment routes. Отчёт не утверждает готовность магазина.
- [ ] Commit: `chore: bootstrap local foundation API and PostgreSQL`.

### Task 2: Минимальная Alembic schema и synthetic catalog

**Owner:** Backend/Ozon, Architect review DB. **Зависимость:** Task 1.
**Files:** Create packages/database/alembic.ini, alembic/env.py, alembic/versions/0001_catalog.py, 0002_guest_drafts.py, src/elton_database/models/catalog.py, guest.py, drafts.py, repositories/catalog.py, fixtures/catalog.synthetic.json, scripts/seed_demo.py, tests/test_foundation_schema.py.
**Interfaces:** CatalogRepository.load_products(ids:list[UUID],for_update:bool=False) →list[CatalogRow]; lock order sorted UUID; seed_demo(session:Session,fixture_path:Path) →None. Fields/FKs/CHECKs exactly DATABASE stage1. Idempotency draft_id preallocated, NOT NULL deferred FK; cannot commit missing draft.

- [ ] Написать tests против PG: duplicate SKU/cart item/idempotency scope запрещены; quantity0/negative/overflow rejected; missing deferred draft FK fails at commit; referenced product hard-delete refused.
- [ ] Запустить `uv run pytest packages/database/tests/test_foundation_schema.py -q`; ожидается FAIL до migrations.
- [ ] Реализовать models/migrations/repos, immutable BOM pointer ownership и synthetic seed по CAT-01; не добавлять commercial/customer tables.
- [ ] Выполнить `uv run alembic -c packages/database/alembic.ini upgrade head` на пустой isolated DB, затем progression0001→0002; запустить schema tests. Ожидается PASS/один migration owner.
- [ ] Запустить `uv run python scripts/seed_demo.py`; query fixture должен дать категории CAT-01, single товары и bundle с компонентами, без PII/stock/reviews.
- [ ] Commit: `feat: add foundation catalog cart and draft schema`.

### Task 3: Каталог, guest proof и versioned PG cart

**Owner:** Backend/Ozon. **Зависимость:** Task 2.
**Files:** Create apps/api/src/elton_api/catalog/{schemas,routes,service}.py, guest/{schemas,routes,service,csrf}.py, cart/{schemas,routes,service}.py, packages/database/src/elton_database/repositories/{guest,cart}.py, apps/api/tests/test_guest_cart.py, test_catalog.py; Modify main.py для router registration.
**Interfaces:** resolve_guest(request:Request,session:Session) →GuestPrincipal; require_csrf(request,principal) →None; get_cart(principal:GuestPrincipal) →CartDTO; set_quantity(principal,product_id:UUID,quantity:int,expected_version:int) →CartDTO; delete_item(principal,product_id,expected_version) →CartDTO. Catalog DTO/query/pagination по API.md.

- [ ] Написать server tests с двумя cookie sessions: чужая корзина недоступна; CSRF/Origin wrong→403; stale If-Match→409, missing→428; no session→401; revoked/expired session denied.
- [ ] Написать catalog/cart test: цена 10000×qty2→amount_minor"20000"; customer-supplied price rejected; inactive/missing-price line имеет issue, goods_total=null/can_quote=false; product cost/reviews/FBO qty не выдаются.
- [ ] Запустить `uv run pytest apps/api/tests/test_guest_cart.py apps/api/tests/test_catalog.py -q`; ожидается FAIL.
- [ ] Реализовать guest token hash/expiry, persistence7 days recommendation, bound CSRF, scoped origins, PG cart locks/version/ETag и server current pricing.
- [ ] Повторить tests; ожидается PASS, после API restart тот же cookie читает прежнюю cart из PG.
- [ ] Commit: `feat: persist protected guest cart and catalog API`.

### Task 4: Immutable quote и атомарная заявка

**Owner:** Backend/Ozon; Architect review transaction. **Зависимость:** Task 3.
**Files:** Create apps/api/src/elton_api/drafts/{schemas,routes,quote_service,save_service}.py, packages/database/src/elton_database/repositories/drafts.py, apps/api/tests/test_draft_money.py, test_draft_idempotency.py, test_draft_access.py; Modify main.py.
**Interfaces:** create_quote(principal:GuestPrincipal,cart_version:int) →DraftQuoteDTO; save_draft(principal,command:DraftSaveCommand,idempotency_key:str) →SavedDraftResult(dto:DraftDTO,replayed:bool); get_draft(principal,draft_id:UUID) →DraftDTO. Contact/address normalization and request_hash includes all DTO fields. Error codes/version/expiry/replay ordering по API/DATABASE, no external adapter injected.

- [ ] Написать money/BOM tests с synthetic components10000/20000, bundle price29000, bundle qty2:
```python
assert draft.goods_total.amount_minor == "58000"
assert draft.delivery.amount is None
assert draft.payable_total is None
assert [c.total_quantity for c in draft.items[0].components] == [2, 2]
assert draft.items[0].components[0].base_unit_price.amount_minor == "10000"
```
После каталога price30000/BOM qty3 saved snapshot остаётся 58000/2; до save те же изменения →QUOTE_CHANGED. Товар 9007199254740993 minor×1 сохраняется строкой без JS precision loss; bigint multiplication overflow→422, ничего не сохранено.
- [ ] Написать concurrency/retry tests с actual PG: same key/body parallel→one draft, same ID; same key/different contact→409; committed save затем quote expiry→same ID201 replay; new key consumed quote→QUOTE_USED; before commit crash→zero draft; after commit lost response→one; foreign/expired session→404/401 до replay disclosure.
- [ ] Написать version races: cart edits→CART_CHANGED; stale quote→QUOTE_EXPIRED; inactive component→QUOTE_CHANGED/validation conflict; admin/catalog lock race даёт валидный старый snapshot либо conflict, никогда смешанный BOM/price.
- [ ] Запустить `uv run pytest apps/api/tests/test_draft_money.py apps/api/tests/test_draft_idempotency.py apps/api/tests/test_draft_access.py -q`; ожидается FAIL.
- [ ] Реализовать signatures, stable lock order, quote15min recommendation и atomic snapshot/idempotency/deferred FK/consumption; state только saved. Fail guards не создают платежи/провайдерские rows/events.
- [ ] Повторить tests: ожидается PASS; schema/API DTO соответствуют exact Money/null totals. Backend reviewer подтверждает replay ordering и deferred-FK completion.
- [ ] Commit: `feat: save immutable idempotent local checkout drafts`.

### Task 5: Защищённые admin catalog commands и draft reads

**Owner:** Backend/Ozon; Architect/BA review ADM-01. **Зависимость:** Task 4. До решения ADM-01 допускаются DTO/repositories и negative authorization tests; login implementation/публичный admin остаются blocked.
**Files:** Create packages/database/alembic/versions/0003_admin_access.py, src/elton_database/models/admin.py, repositories/admin.py; apps/api/src/elton_api/admin/{schemas,routes,auth,service}.py; apps/api/tests/test_admin_access.py, test_admin_catalog.py; Modify main.py.
**Interfaces:** require_admin(request:Request,permission:str) →AdminPrincipal; update_product(admin,product_id,patch:ProductWriteDTO,expected_version:int) →ProductAdminDTO; set_site_price(admin,product_id,price:Money,expected_version) →ProductAdminDTO; replace_bundle(admin,product_id,components:list[BundleComponentInput],expected_version) →BundleDTO; list_drafts(admin,cursor,created_from,created_to) →DraftPageDTO. Permissions catalog.read/catalog.write/drafts.read.

- [ ] Зафиксировать ADM-01 approval/первичную выдачу и recovery до auth implementation; отсутствие решения не заменить mock/open admin. Audit при необходимости отдельной ранней additive migration.
- [ ] Написать tests: guest/customer cookies→401/403 admin; wrong permission/CSRF/Origin→403; stale product version→409; unauthorized draft list не раскрывает PII; reject arbitrary paid/delivered/FBO payload.
- [ ] Написать catalog mutations tests: обновление site price/BOM меняет aggregate version, не saved snapshot; bundle qty positive, duplicate SKU normalized, nested bundle rejected как proposed BR-12 validation; полное изменение audit без PII/secrets.
- [ ] Запустить `uv run pytest apps/api/tests/test_admin_access.py apps/api/tests/test_admin_catalog.py -q`; ожидается FAIL.
- [ ] После ADM-01 approval реализовать отдельные email/password/server sessions с hash/rotation/revoke, CSRF и runtime bootstrap без default password; catalog/draft read commands строго через permission service.
- [ ] Upgrade0002→0003 и повторить tests; PASS закрывает backend часть S1-05, не гарантирует frontend/full S1-05.
- [ ] Commit: `feat: protect admin catalog and draft administration`.

### Task 6: Проверяемая загрузка фото и MP4 товарного видео

**Owner:** Backend/Ozon; QA/security review. **Зависимость:** Task 5 approved access.
**Files:** Create apps/api/src/elton_api/media/{schemas,routes,service,image_processor,video_processor,local_storage}.py, apps/api/tests/test_admin_media.py, tests/fixtures/media.synthetic/ (generated safe JPEG/WebP/MP4 + malformed fixtures); Modify config.py/main.py.
**Interfaces:** validate_image(file:BinaryIO,limits:MediaLimits) →ValidatedMedia; validate_video(file:BinaryIO,limits:MediaLimits) →ValidatedMedia; publish_product_media(admin,product_id,file,alt_text,position,expected_version) →MediaDTO. Limits exact API recommendations; storage UUID outside web-root; relative clean media URL.

- [ ] Написать file tests: valid synthetic raster and MP4 become accessible gallery media; spoofed MIME/SVG/polyglot/oversize/pixel bomb/invalid codec/container/traversal→reject and no public pointer; unauthorized/CSRF→reject; URL field rejected and zero URL fetch.
- [ ] Запустить `uv run pytest apps/api/tests/test_admin_media.py -q`; ожидается FAIL.
- [ ] Зафиксировать FFmpeg/ffprobe dependency/runtime version и decoder policy; безопасный MP4 H.264/AAC (или no-audio) transcode/remux с удалением metadata. Вызывать subprocess argv без shell, ограничивать CPU/time/output size; JPEG/PNG/WebP decode/re-encode, EXIF removed.
- [ ] Реализовать quarantine→validated derivative→atomic media pointer+audit/version, streamed size caps, nosniff serving; failed pipeline не публикует bytes. video decoder unavailable означает блок video capability, явный незакрытый CAT-05/S1-01 video gate.
- [ ] Повторить tests и вручную проиграть synthetic MP4 в проверяемых браузерах demo; ожидается PASS/видео с корректным MIME, metadata безопасны.
- [ ] Commit: `feat: validate product image and video uploads`.

### Task 7: Storefront/admin UI и same-origin API client

**Owner:** Frontend; shared OpenAPI меняет Backend с Architect review. **Зависимость:** Tasks3/4/5/6; каталог/cart/draft UI может готовиться до admin auth approval.
**Files:** Create package.json, pnpm-workspace.yaml, pnpm-lock.yaml; apps/storefront/package.json, next.config.ts, app/layout.tsx, app/page.tsx, app/catalog/page.tsx, app/products/[slug]/page.tsx, app/cart/page.tsx, app/checkout/page.tsx, app/result/[id]/page.tsx, app/api/v1/[...path]/route.ts; apps/admin/package.json, next.config.ts, app/layout.tsx, app/login/page.tsx, app/products/page.tsx, app/products/[id]/page.tsx, app/drafts/page.tsx, app/drafts/[id]/page.tsx, app/api/v1/[...path]/route.ts; packages/ui/src/{money,gallery,form-errors}.tsx; packages/api-client/{package.json,openapi.json,src/generated.ts,src/client.ts,src/proxy.ts}; tests/frontend/proxy.test.ts.
**Interfaces:** generate active OpenAPI TS types; apiClient.getCart()/createDraftQuote(cart_version)/saveDraft(command,key)/getDraft(id)/admin commands используют их, без manual schemas. proxy(request:Request,context:{path:string[]}) →Response forwards permitted headers/cookie/set-cookie/original Origin к fixed server API URL. Catalog slug route использует GET /products/by-slug/{slug} из active API inventory.

- [ ] Добавить будущие scripts generate:api/check:api/typecheck/build/test; pnpm stable version/locks по official supported docs; сохранить owner root manifests за Frontend с Backend review Python/TS boundary.
- [ ] Написать proxy tests: cookie/set-cookie/CSRF/Origin сохраняются, client upstream URL rejected, authenticated response no-store. `pnpm test -- tests/frontend/proxy.test.ts` должен FAIL до implementation.
- [ ] Реализовать app scaffolds/proxy/client; показать hero→карточки CAT-01 меню, responsive search/category/demo sorts, фото/MP4/fullscreen gallery, attributes/related, unknown stock/not-connected delivery; no fake reviews/Sale/Новинки/Хиты.
- [ ] Реализовать persistent server cart/version errors и demo contact/address→quote→explicit save confirm→result. Money через BigInt/string formatting, delivery «Пока не подключена», goods_total «Стоимость товаров», no complete payable total. Conflict получает fresh quote только после повторного user confirmation.
- [ ] Реализовать same body/key retry и bounded pending DraftSaveCommand/key в sessionStorage только для reviewed synthetic demo (≤1 часа, удалить body после definitive result/error); full reload повторяет exact сохранённый body/key. Auth cookie не хранится в JS. При истёкшем local record не делать automatic new save. Добавить full-reload после lost successful response в E2E Task 8; result exact message API.md; user-readable inline errors без raw payload. Demo synthetic values/banner, no SMS/account prerequisite.
- [ ] После Task 5/6 реализовать admin guarded UI product/siteprice/BOM/media/draft list/detail. Полномочия обеспечивает API; UI не подменяет protected access.
- [ ] Выполнить `pnpm generate:api`, `pnpm check:api`, `pnpm typecheck`, `pnpm build` и proxy tests; ожидается PASS. Проверить cookie persistence через настоящий UI→API→PG при restart браузера и denial в чужой сессии; full browser assertions Task 8.
- [ ] Commit: `feat: build foundation storefront and protected admin UI`.

### Task 8: Полная локальная приёмка и необходимые CI checks

**Owner:** QA/DevOps; дефекты возвращать component owner. **Зависимость:** Tasks1…7, ADM-01 approved для полного S1-05.
**Files:** Create playwright.config.ts, tests/e2e/foundation.spec.ts, tests/e2e/admin.spec.ts, tests/e2e/proxy-session.spec.ts, apps/api/tests/test_disabled_capabilities.py, .github/workflows/foundation-checks.yml, docs/reports/stage1-foundation-acceptance.md. Modify QA/DEPLOYMENT/WORKFLOW только evidence sections в отдельном reviewed PR.
**Interfaces:** local start commands/API URLs/seeds previous tasks; actual PG, synthetic media, two independent browser contexts. CI no external credentials/provider fixtures; scripts отчёта не заявляют Ozon contract pass.

- [ ] Написать E2E: main/category/PDP/gallery/video на mobile/desktop; guest add/edit/resume cart после закрытия persistent browser profile; synthetic form/save/result; refresh/lost-response/full reload duplicate same id с тем же restored body/key; чужой cookie/ID→404; exact state/message/null totals.
- [ ] Написать admin E2E: approved login, catalog price/BOM/media edits, draft list/detail, saved snapshot unchanged; guest scope/CSRF wrong deny.
- [ ] Написать direct disabled requests tests: payment/delivery/SMS/refund/promotion/callback attempts не вызывают ни одного external client и не создают payment/fulfillment/refund/ledger/purchase/customer/reservation facts; explicit unsupported errors, no mock success.
- [ ] Выполнить `uv run pytest apps/api/tests packages/database/tests -q`, `pnpm check:api`, `pnpm typecheck`, `pnpm build`, `pnpm exec playwright test`; до реализации tests должны выявлять недостающее поведение, после fixes ожидается PASS. Повторять только gates изменённого поведения/конкретного дефекта.
- [ ] Добавить CI для этих check commands, migrations empty/progression PG и secrets/dependency review; fork jobs без runtime/provider secrets. Не добавлять Ozon sandbox jobs, пока доступ не предоставлен.
- [ ] Записать S1-01…06 фактические результаты/commit/migrations/окружение/ограничения: ADM-01 unresolved/video pipeline incomplete означает незакрытый gate; документы/моки не pass. Production/облачный preview не публиковать этой задачей.
- [ ] Commit: `test: verify foundation persistence access and disabled commerce`.

## Самопроверка плана и handoff

Покрытие: CAT-01…05 Tasks2/3/6/7/8; ORD-01…03 Tasks3/4/7/8; ADM-01/03/05/06 Tasks5/6/7/8; S1-04 Tasks1/4/8. BR-15/FBO/real Pay/Delivery/SMS/profile/return/refund/business retention — отложены с сохранёнными gates. Five Review Focus cases привязаны к meaningful PG/browser/upload tests. DTO/signatures/types и null totals одинаковы с API/DATABASE; цены/BOM не вычисляются заново в saved result.

План не выполнялся. До исполнения — Backend/Architect review ADR-013 и зависимый ADM-01 approval; технические demo DTO/TTL/media параметры пройти review без приписывания решения заказчику. По завершении основы — отдельная задача публикации synthetic demo и OZ-G1 official onboarding/contract access, без обещания provider approval.
