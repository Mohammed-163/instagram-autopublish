# database/migrations/

Every future schema change goes here as a new, numbered `.sql` file.

**Never** edit `schema.sql`, `indexes.sql`, `views.sql`, `triggers.sql`, or
`functions.sql` after the project has run once against a real database —
those baseline files were already applied as version `1` and are only kept
around as the readable "what version 1 looked like" reference. Any change
after that must be a new migration file, or environments will diverge.

## Naming

```
NNNN_short_description.sql
```

* `NNNN` is a zero-padded, strictly increasing integer starting at `0002`
  (`0001` is reserved for the baseline files).
* Numbers must be unique and are applied in ascending numeric order.
* Each file runs inside a single transaction — if any statement in it fails,
  the whole file is rolled back and the version is not recorded.

Example: `0002_add_hashtags_to_posts.sql`

```sql
ALTER TABLE posts ADD COLUMN hashtags TEXT;
CREATE INDEX IF NOT EXISTS idx_posts_hashtags ON posts (hashtags);
```

## How it gets applied

`database/migrate.py` (run automatically at the start of every workflow, or
manually with `python -m database.migrate`) discovers every file here,
compares it against the `schema_version` table, and applies anything newer
than the current version — in order, one transaction per file. Nothing
manual is required beyond adding the file and committing it.
