# Stage 1 closure: active specification and ordered plan

Date: 2026-10-07. Baseline `0c8697a5102e6b9ff56e95889f319d8906f09d81`. Customer instruction: implement the selected outstanding gates, launch the full Stage 1 MVP locally. ADM-01 approval recorded as BA-AUTH-01/ADR-014. This extends the 2026-10-06 foundation plan; existing CAT/ORD/ADM IDs and BR-27/S1-01…06 remain authoritative. No production approval.

## Active boundaries

- Local synthetic guest/contact/address/cart/draft scenario; server money/snapshots/idempotency/ownership remain unchanged.
- One owner admin email/password/Argon2id/server session, protected local CLI bootstrap/reset, no public signup/recovery. Reset revokes sessions; guest/admin cookies/proofs and CSRF scopes isolated.
- Full decode, EXIF transpose, bounded raster processing, fresh metadata-free server derivative, durable storage then clean DB/audit; no raw publication. JPEG/PNG/WebP max10 MiB, dimension8192, pixels40 million; reject corrupt/spoofed/animated/bomb/active files. Video disabled until its separately reviewed actual pipeline.
- Separate optional server read-only Seller/Performance contract-verified adapter/CLI. No customer/posting/return ingestion or provider mutation. Catalog import stages external IDs/content separately; owner site prices/BOM do not change automatically. FBO observations record model/source/semantics/time; unknown/failed/zero differ, failure preserves prior success. Reviews not persisted/published until Q-08; API key alone is insufficient. Performance facts remain channel ozon_marketplace, no site revenue substitution.
- The dated read-only extension supersedes prior broad “no Ozon runtime at all” foundation language only for this explicit adapter task. Guest/cart/draft/admin auth remain independent with zero outbound provider calls. All commercial capabilities stay false.

## Auth contract

API.md defines login200/session200 `AdminSessionDTO{id,email,permissions,csrf_token,expires_at}`, logout204. Email trim/lowercase≤254; login password untouched≤128, secret/redacted DTO. Bootstrap/reset new password length12…128. Token random/high entropy, PG hash only, Argon2id hash for password, dummy verification and generic401 INVALID_CREDENTIALS, exact admin Origin, bounded IP/account429 limit. Configured session expiry/rate limits are reviewed local technical parameters, not production business retention. Cookie elton_admin Path=/api HttpOnly SameSite=Lax; Secure=false only loopback HTTP. No raw token JSON/localStorage. All auth responses no-store.

CLI bootstrap serializes under PG lock, refuses second owner, atomically provisions three permissions catalog.read/catalog.write/drafts.read and sanitized audit. Email runtime input; password hidden prompt/protected ignored secret file; never password argument/default/source/log. Reset explicitly targets that owner and revokes all sessions. Initial credentials handed to user by local protected file path or safe input instructions; never plaintext report.

## Work and owners

1. Architect owns these shared docs/ADR; Backend reviews API/DB/auth before code. No parallel writes to the same files.
2. QA/DevOps supplies isolated loopback PostgreSQL demo/test DBs, migration/seed/readiness, reproducible local start/stop and synthetic restore check. Tests must guard reset target; never use demo DB for destructive test cleanup.
3. Backend implements login/session/logout/bootstrap/reset, permissions/negative auth tests and missing protected product list/read/create operations. Uses existing schema; any required additions through reviewed Alembic only.
4. Backend/media owner implements trusted raster pipeline plus rollback/clean publication tests. Frontend after API freeze implements working protected login/logout/product/price/BOM/media/draft forms and verified galleries.
5. Ozon owner verifies current official contracts/relevant repo files and account scopes; implements allowlisted safe reads with deadlines, bounded429/5xx retry, runtime-only secrets, sanitized fixtures/error classes. Records live checks separately from mock contracts. Adapter failure cannot break the core demo path.
6. QA runs actual PG migration/persistence/concurrency and actual mobile/desktop browser proxy/API/PG guest+admin flow; immutable snapshots, ownership, CSRF, duplicate saves, media, disabled zero-effects checks. Build/type/OpenAPI/proxy checks, relevant secret scan and restore evidence.
7. Component owners fix findings; acceptance report links evidence for every S1-01…06. Required PG/E2E skips are incomplete, not pass. Then start PG/API/storefront/admin, verify readiness200/populated catalog/save/admin mutation, give local URLs and safe owner-access instructions.

## Remain Stage 2

Real Pay/Delivery/website FBO order, guaranteed stock/reservation/fulfillment, SMS/customer account, callbacks, cancel/refund/return, bundle fulfillment/net refund allocation, live customer PII/public/commercial release. Their Q/OZ/ARCH/QA/DEPLOYMENT gates are preserved. Local saved drafts are never auto-submitted after credentials/flags appear.

## Acceptance evidence

S1-01 catalog/PDP/media/mobile; S1-02 durable guest cart; S1-03 immutable idempotent draft including BOM; S1-04 honest no-pay/delivery/zero provider effects; S1-05 real protected catalog/media/price/BOM/draft admin and ownership; S1-06 actual shared runtime with synthetic demo and reproducible start. Report exact current commands/results/runtime/schema, limitations and live Ozon support status. HTML shell200 or fixtures alone do not close these gates.
