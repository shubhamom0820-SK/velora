# Velora

Velora is a web-first dating app for India. Women use it free; men buy credits. Every conversation
starts as a **Thread** that expires in 24 hours, and if both people tap "Tie the knot" it becomes a
**Velora** — permanent and free forever. Permanence is granted by the other person, never bought.
The web app is Next.js on Vercel; the API and worker are FastAPI on Fly.io Singapore, backed by
PostgreSQL + PostGIS and Redis in Mumbai, so users' data stays in India (D-048).

```
make dev
```

Run `make` on its own to see every target. `CLAUDE.md` is the working agreement for this repo and
`docs/05-PLAN.md` is the only list of what gets built.
