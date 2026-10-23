"""
Database layer for the Instagram Auto-Publish System.

Everything related to persistence lives here:

    database/client.py             -> engine / session factory (Supabase Postgres)
    database/migrate.py             -> CLI entrypoint, run at startup: `python -m database.migrate`
    database/migration_manager.py   -> discovers + applies migrations/*.sql automatically
    database/schema.sql             -> baseline table definitions (applied by migration 0001)
    database/indexes.sql            -> baseline indexes               (applied by migration 0001)
    database/views.sql              -> baseline views                 (applied by migration 0001)
    database/triggers.sql           -> baseline triggers               (applied by migration 0001)
    database/functions.sql          -> baseline functions              (applied by migration 0001)
    database/migrations/            -> ordered, numbered *.sql migration files (source of truth)
    database/models/                -> typed SQLAlchemy 2.x ORM models
    database/repositories/          -> the ONLY layer allowed to talk to the database directly

Nothing outside `database/` should ever import SQLAlchemy or write raw SQL.
Application code talks to `database.repositories.*` only.
"""
