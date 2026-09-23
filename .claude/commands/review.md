Review the uncommitted changes for task $ARGUMENTS. Do not fix anything unless I ask.

1. `git status` and `git diff` — list every changed file. Flag any file not in the approved plan.
2. Check each acceptance item for task $ARGUMENTS in `docs/05-PLAN.md`: pass or fail, with evidence.
3. Walk `docs/07-CHECKLISTS.md` section A, plus B (if an endpoint changed), C (if a migration was
   added), D (if a screen changed) and E (if auth, wallet, payments or uploads were touched).
4. Search the diff for these and report every hit:
   - literal credit amounts, prices, limits or durations (should come from `action_prices`/`app_config`)
   - `datetime.now`, `time.sleep`, `import requests`, `psycopg2`
   - hex colours outside `web/src/styles/tokens.css`
   - `print(` in Python, `console.log` in web code
   - `wallets` balance written anywhere outside `wallet/service.py`
   - `body_raw`, phone, OTP or token values in any response schema or log call
5. Run `make lint test` and report the result.
6. End with a verdict: READY or NOT READY, and the exact list of things to fix.
