"""The dev seed: `make seed` (T-1.15, D-064).

Writes the prototype's 20 profiles and three test accounts into the local
stack's database, and nowhere else. Before writing a row it checks three things,
each an allowlist (rule 16): `ENV` is local, `DATABASE_URL`'s host is this
machine, and the database carries the marker `make infra-up` stamps on it. An
SSH tunnel makes another database look local by its address; the marker asks
the database itself.

This package lives outside `app/` on purpose: `.dockerignore` keeps it out of
the API image, and CI checks the image has none, so no bug in a guard can run it
in production.

Running it again changes nothing. To start over: `make infra-reset`, then
`make infra-up migrate seed`. There is no targeted delete: from T-5.1 the ledger
refuses one (T-1.12).
"""
