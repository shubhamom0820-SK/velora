#!/bin/bash
# Creates the test database alongside the dev one. Runs once, on first init of
# the data volume. Extensions are NOT created here — migration T-1.8 owns them
# and applies them to whichever database Alembic is pointed at.
#
# Since P-55 each test run creates a database of its own (api/tests/infra.py),
# so nothing on main uses velora_test; it stays for branches cut before P-55.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
	CREATE DATABASE velora_test OWNER "$POSTGRES_USER";
SQL

echo "init: created database velora_test"
