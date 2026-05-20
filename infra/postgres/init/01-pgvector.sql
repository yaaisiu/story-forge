-- Mounted into /docker-entrypoint-initdb.d/ in docker-compose.yml.
-- Runs once on first Postgres data-directory init. Idempotent thanks to IF NOT EXISTS.
CREATE EXTENSION IF NOT EXISTS vector;
