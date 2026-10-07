# Database

Планируемый Python пакет SQLAlchemy models/repositories и Alembic migrations. Владелец Backend/Ozon с Architect review. Схема — [DATABASE](../../docs/DATABASE.md); сейчас миграций и подключённой БД нет.

Это не npm workspace. Одна схема — одна система миграций. При использовании Supabase тот же Alembic управляет schema; не создавать одновременно Prisma/Supabase CLI schema migrations. Credentials только runtime. Supabase Data API, если будет открыт, требует отдельного RLS/access review и не обходит core API.
