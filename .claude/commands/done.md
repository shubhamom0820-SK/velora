Finish task $ARGUMENTS.

1. Run `make lint test`. If anything fails, stop and report — do not continue.
2. If the API changed, confirm `make types` was run and `web/src/types/api.ts` is in the diff.
3. In `docs/05-PLAN.md`, tick every checkbox belonging to task $ARGUMENTS only. Touch nothing else
   in that file except the "Proposed tasks" section.
4. Stage the changes and commit using the task's **Commit** line from the plan as the message.
5. Show `git log -1 --stat`.
6. Tell me the next task: the first unticked task in `docs/05-PLAN.md` whose Needs are all ticked.
   Say its ID and title only. Suggest I start a fresh session for it.
7. Push the branch: run `git push -u origin HEAD`. If the push fails because
   no remote is configured, tell me instead of guessing a URL.
