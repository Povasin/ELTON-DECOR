# QA report: MP4 media pipeline (CAT-05 / S1-01)

Дата проверки: 2026-10-07
Проверяющий профиль: Backend / QA / DevOps / Security
Базовый commit: текущая рабочая ветка `feat/admin-media-refresh`.

## Текущий статус

MP4-часть CAT-05/S1-01 **закрыта для локальной демонстрации**. Server-side pipeline, admin/storefront UI, PostgreSQL persistence и browser playback проверены на синтетическом файле. Для preview/production ещё нужно зафиксировать тот же FFmpeg runtime в образе/manifest.

Реализовано в backend и UI:

- `video_processor.py` вызывает `ffprobe` и `ffmpeg` через argv без shell, с timeout, одним worker thread, размером до 50 MiB и duration до 60 секунд;
- принимается только MP4 с одним H.264 или HEVC video stream и максимум одним AAC audio stream, без subtitle/data/attachment streams;
- `ffmpeg` декодирует H.264/HEVC и создаёт UUID keyed clean H.264 MP4 derivative с удалёнными metadata/chapters, после чего output повторно пробируется;
- upload публикует `media_type=video`, metadata и audit/version atomically with the DB transaction; failure cleans quarantine/derivative;
- public media route отдаёт только clean DB-backed `video/mp4` (image behaviour preserved);
- invalid/non-MP4 or unavailable decoder/encoder fail closed and never create a clean pointer.
- админка принимает `video/mp4` через общий защищённый upload и показывает clean-видео с controls;
- storefront PDP отображает clean image/video gallery и `<video controls preload="metadata">`.

Проверено локально:

- runtime использует FFmpeg/ffprobe 9.0.2; для preview/production версию и checksum нужно зафиксировать в deployment image/manifest;
- admin proxy upload → PostgreSQL clean row → public `video/mp4` response прошёл;
- storefront PDP показал `<video controls>` с clean URL, `readyState=4` (`HAVE_ENOUGH_DATA`) и `video.error=null`;
- временная synthetic media row и clean-файл удалены после проверки.

## Проверки, которые должны закрыть gate

| Проверка | Ожидаемый результат | Evidence |
|---|---|---|
| Valid MP4 upload | `201 MediaDTO`, `type=video`, путь указывает на clean derivative | pytest/TestClient + PostgreSQL/storage fixture |
| Container/MIME spoof | `422 MEDIA_INVALID`; clean row и public file отсутствуют | real bytes, не только заголовок |
| Unsupported codec/container | `422 MEDIA_INVALID` или согласованный `409 CAPABILITY_DISABLED`; ничего не публикуется | ffprobe + transcoder logs without raw payload |
| Size/duration limits | превышение 50 MiB или 60 sec отклоняется; quarantine очищается | generated synthetic fixtures |
| Audio/video policy | лишняя audio track или неподдержанный profile следует принятой policy | ffprobe metadata |
| Remux/transcode | опубликованный файл проходит повторный ffprobe и имеет server-selected UUID key | clean storage + DB row |
| Failure cleanup | ошибка decoder/transcoder не оставляет clean row, public ref или orphan quarantine | DB rollback and filesystem assertions |
| Product version | upload/delete uses `If-Match`; stale version returns `409 VERSION_CONFLICT` | concurrent API test |
| Capability taxonomy | disabled configuration returns `409 CAPABILITY_DISABLED`, invalid media returns validation problem | API contract test |
| Browser playback | product page renders `<video controls>`, `currentSrc` is `/api/v1/media/clean/...`, `readyState >= HAVE_METADATA`, `video.error === null` | opt-in `tests/e2e/video.spec.ts` |

## Required security evidence

1. Raw upload stays outside the web root and is never returned from an API response.
2. Server determines the final content type and storage key; client filename and MIME are advisory only.
3. MP4 metadata is bounded before decode; duration, dimensions, streams, codec and container are checked from trusted tool output.
4. The clean derivative is published only after a successful atomic DB/storage operation and audit entry.
5. Logs contain correlation data and validation result, but no raw media bytes, credentials, cookies or full personal data.
6. Public route refuses missing DB row, non-clean `scan_state`, symlink, path traversal and a media type outside the allowed public video type.

## Commands run

Runtime and application checks were run locally without exposing credentials:

```text
FFmpeg/ffprobe 9.0.2 (Gyan.FFmpeg.Shared, winget; installer hash verified)
ffmpeg/ffprobe version        -> 9.0.2-full_build
apps/api/tests                -> 131 passed, 35 skipped
focused media/video tests     -> 31 passed
frontend unit tests           -> 17 passed
admin + storefront tsc        -> passed
admin proxy synthetic upload  -> 201, type=video, clean public GET 200 video/mp4 nosniff
admin API HEVC upload         -> 201, transcoded clean public GET 200 video/mp4 nosniff
browser video assertion       -> clean URL, controls=true, readyState=4, error=null
```

Backend tests include subprocess policy stubs and a synthetic MP4-shaped fixture. They prove argv, limits, stream policy, metadata removal flags, output re-probe, cleanup and fail-closed unavailable runtime; they do not replace a real FFmpeg integration run.

The browser check `tests/e2e/video.spec.ts` remains opt-in for CI; the local run above used the same assertions through the in-app browser against the running PostgreSQL/API/storage stack.

## Remaining release hygiene

- Pin FFmpeg/ffprobe 9.0.2 and checksum in the deployment image/manifest; local winget installation is evidence for this machine only.
- Keep the synthetic fixture generated during the test out of the demo catalog and never commit production media or secrets.
- Run the opt-in Playwright job in CI with a reviewed browser/runtime image before preview release.
