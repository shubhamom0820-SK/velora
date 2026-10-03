-- Stamps the local stack's database as local (T-1.15, D-064).
--
-- `make infra-up` runs this through psql inside the db container, so it can only
-- ever reach that container's own database: never staging or production,
-- whatever DATABASE_URL says, and never velora_test.
--
-- The dev seed writes only to a database carrying this exact comment: a tunnel
-- can make another database's address look local, but it can't give that
-- database this comment. Keep the text identical to LOCAL_DATABASE_MARKER in
-- api/seed/run.py; a test there reads this file and fails if they differ.
DO $$
BEGIN
  EXECUTE format(
    'COMMENT ON DATABASE %I IS %L',
    current_database(),
    'local-dev: stamped by make infra-up (infra/postgres/stamp-local.sql). The dev seed writes only to a database carrying this (T-1.15, D-064).'
  );
END
$$;
