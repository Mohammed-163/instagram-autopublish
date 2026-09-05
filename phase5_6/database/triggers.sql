-- =============================================================================
-- triggers.sql — baseline triggers (version 1)
-- =============================================================================
-- Requires set_updated_at() from functions.sql, so functions.sql must run first
-- (migration_manager applies schema.sql -> indexes.sql -> functions.sql ->
-- triggers.sql -> views.sql, in that order).

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_posts_set_updated_at ON posts;
CREATE TRIGGER trg_posts_set_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
