# Submission Checklist

## Required artifacts
- [ ] **Public GitHub repo** — visibility set to Public.
- [ ] **CI badge green** on the default branch (Actions tab shows the latest commit passing).
- [ ] **Live URL in the repo's About → Website field** — `https://agentgate-ebon.vercel.app` (first thing judges see on the repo page).
- [ ] **5-minute pitch video** — under 5:00, screen + voice, uploaded; link added to README and the submission form. Script: [video-script.md](video-script.md).
- [ ] **Architecture doc** — [architecture.md](architecture.md).
- [ ] All docs cross-linked from the README (they are).

## Verify before submitting
- [ ] `make check` passes locally (lint + types + 79 tests).
- [ ] `make eval` runs and prints metrics; a run is persisted (Metrics page not empty).
- [ ] **Fresh-clone test on a machine that isn't your dev box** — clone, `.venv`, `pip install`, fill `.env`, `make migrate && make seed && make seed-attacks`, `make demo` completes in ~5 min.
- [ ] **Independent chain verification works:** `curl <url>/api/audit/export > chain.json && python3 scripts/verify_chain.py chain.json` prints `CHAIN INTACT`.
- [ ] **Open the live URL on a phone** — dashboard is readable; tables scroll, nothing overflows the viewport.
- [ ] Every claim in the README links to live evidence or a test.

## Never-empty demo state
- [ ] Deployment has accumulated real decisions (Overview counter > 0), a non-empty audit chain, recorded agent sessions, and at least one eval run. A judge opening the URL cold sees a populated dashboard, not empty tables. *(Currently 240+ decisions, chain intact, 3 eval runs.)*

## During the judging window
- [ ] Monitor Vercel invocation usage (Hobby limits) and Neon free-tier storage/compute.
- [ ] Keep Razorpay in **test mode** — never live keys anywhere.
- [ ] Once submitted, **freeze the production deployment** (stop pushing to `main`) so the reviewed state doesn't drift.

## The two Definition-of-Done acceptance tests
1. **Stranger + URL only** → can explain the project back to you after 60 seconds. (Overview page must carry the whole thesis.)
2. **Stranger + repo only** → runs `make demo` successfully in 5 minutes. (README quickstart must be complete and correct.)

## Panel rehearsal
Deliver the [video script](video-script.md) aloud in 5 minutes without notes. If you can do that, you can do the panel.
