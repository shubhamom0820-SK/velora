Start task $ARGUMENTS from `docs/05-PLAN.md`. Follow these steps in order and do not skip any.

1. Read `CLAUDE.md` in full. Then read the section for task $ARGUMENTS in `docs/05-PLAN.md`.
2. Check every task in its **Needs** line is ticked `[x]`. If any is not, stop and tell me which.
3. Read only the parts of `docs/01-DECISIONS.md`, `docs/03-SCHEMA.md`, `docs/04-API.md`,
   `docs/02-ARCHITECTURE.md` and `docs/08-DESIGN.md` that this task touches.
4. Reply with a plan, then **stop and wait for my approval**. Do not write or change any file yet.
   The plan must contain:
   - the goal in one sentence
   - every file you will create or modify, with full paths
   - the steps, in order
   - the tests you will write, including which error codes you will test
   - anything unclear or conflicting in the docs (ask, don't guess)
5. After I approve: create branch `t-$ARGUMENTS-<short-name>`. Implement exactly the approved plan.
   If you find necessary work outside it, do not do it — add it under "Proposed tasks" at the
   bottom of `docs/05-PLAN.md`.
6. Run `make lint test`. Fix until both are clean.
7. Report: files changed, test results, and any Proposed tasks you added. Do not tick the checkbox
   and do not commit — that happens in `/done`.
