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
8. Wait for CI on that exact commit: run `scripts/ci-gate` (D-044). It finds the CI run for HEAD's
   SHA on this branch only, never "the latest run on the branch" and never another branch's run of
   the same commit (P-140), waits up to 3 minutes for it to appear and 20 for it to finish, and
   exits 0 only if that run passed. Run it as its own step and read its own exit code.
   - Exit 0: continue.
   - Any other exit: stop here. Show what it printed, leave `main` untouched and the branch
     pushed, and let me decide. Never fast-forward on a failure, a cancelled run, a timeout or
     an error from GitHub.
9. Fast-forward `main`: `git checkout main`, `git merge --ff-only origin/main`, then
   `git merge --ff-only <branch>`, then `git push origin main`. If a fast-forward isn't possible,
   stop and tell me. The push itself refuses unless step 1's `make lint test` passed on this exact
   commit's tree and CI passed for it (`scripts/push-gate`, CLAUDE.md "Landing"): if it refuses,
   stop and show what it printed. Never `--no-verify`.
10. Delete the branch, locally and on origin.

## Manual path: only when GitHub can't be reached (gate exit 4)

This path exists so GitHub being unreachable doesn't turn into an improvised `git merge` that skips
everything above. It is **only** for `scripts/ci-gate` exiting **4**: it couldn't reach or
authenticate with GitHub. That is usually a bad or expired token, not an outage — so step 1 is
always the token.

**Seen once, and open (4 October 2026):** the gate exited 4 while waiting on run 37215825345
(T-5.6's docs, five sessions landing at once). `gh auth status` was fine, `gh api rate_limit`
showed 5,000 of 5,000 left in a fresh window, and the gate, run again at once, went green.
**Hypothesis, not established:** several sessions polling GitHub with one token. The arithmetic
doesn't obviously carry it (five gates polling every 10 s is about 1,800 calls an hour, under
the 5,000), so a secondary limit is as likely. Don't act on it. If it happens again, record the
second occurrence here; a token per session is then the test.

**It is never for a red run, or for anything GitHub answered.** Exit 1 (CI failed, was cancelled,
or ran for another commit) means the commit is not good: fix it on the branch and run `/done`
again. Exit 5 means GitHub answered with an error: read it and fix the cause. Exit 6 means it found
no branch to read: HEAD is detached (a rebase stopped part way?); finish or abort the rebase, back on
the task branch, and run `/done` again. Exit 2 or 3 (no run
appeared, or it didn't finish) means wait and run `scripts/ci-gate` again; if it keeps happening,
stop and ask me. Take this path only when I say so, after you've shown me the gate's exit-4 output.

1. Check the token first: `gh auth status`. If it's expired, missing or lacks a scope, fix it
   (`gh auth login`, or `gh auth refresh -s <scope>`) and run `scripts/ci-gate` again — that is
   the end of it. Go on only if the token is fine and GitHub still can't be reached: the network
   is down, or githubstatus.com reports an incident.
2. On the branch, with a clean working tree (`git status` shows nothing), run CI's checks locally.
   Every one must pass; if any fails, stop.
   - `make lint test`
   - `cd web && pnpm build`
   - `make types && git diff --exit-code -- web/src/types/api.ts`
   - `SKIP=gitleaks uv run --project api pre-commit run --all-files --show-diff-on-failure`
   - `scripts/ci-gate-test`
   - `scripts/ci-vouch-test` and `scripts/ci-e2e-needed-test`

   The full-history secrets scan needs GitHub; CI runs it on `main` once GitHub is back (step 4).
3. Do steps 9 and 10 above, pushing with `VELORA_PUSH_GATE_MANUAL_PATH=1 git push origin main`:
   the landing guard then skips its CI half only, never `make lint test`'s. If the push fails because git can't reach GitHub either, stop and tell
   me: `main` has then moved locally only, and must be pushed before the next task starts.
4. When GitHub answers again, check CI on what went to `main`: `scripts/ci-gate main`. No branch
   run vouches for a commit landed this way, so `main` runs the full CI for it (P-282). If it isn't
   green, tell me at once — `main` is red, and fixing it comes before anything else.
5. In your report, say the gate was bypassed, quote its exit-4 output, and list the local results.
