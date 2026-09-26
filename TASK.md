# SkillIssue — Task Breakdown

| Field | Value |
|---|---|
| Document version | 0.1 (draft) |
| Date | 2026-09-22 |
| Companion docs | `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `MEMORY.md`, `RULES.md` |

## How to use this file

- **Task IDs** are `T-{phase}.{n}` and are stable. Never renumber; append new tasks at the end of a phase.
- **Status:** `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` dropped (keep the row, add reason in Notes).
- **Estimates** are focused hours for one developer who knows the stack. Multiply by about 1.5 for reality (debugging, context switching, tool surprises).
- **Done when** is the acceptance criterion. A task is not done until it is met **and** the Definition of Done in `RULES.md` §19 is satisfied.
- **Process:** work top to bottom within a phase unless Deps says otherwise. One task per branch/PR when practical. Update `MEMORY.md` (status + decisions) at the end of every work session.
- **Scope guard:** MVP = Phases 0–9. Anything in Phases 10+ must not start until the MVP is live (or you explicitly decide otherwise and record it in `MEMORY.md`).
- Do not put a pipe character inside a table cell (the phase totals script parses these tables).

## Phase overview

| Phase | Name | Release | Tasks | Est. hours (sum) | Exit demo |
|---|---|---|---|---|---|
| P0 | Foundations | MVP | 12 | 14.5 | `make dev` boots everything; CI green on an empty pipeline |
| P1 | Source acquisition and filtering | MVP | 11 | 22.0 | CLI prints a file manifest, LOC, and hygiene flags for any public repo |
| P2 | Scanners and sandbox | MVP | 14 | 34.0 | CLI runs all scanners in a locked-down container and emits normalized signals |
| P3 | Sampling and chunking | MVP | 7 | 17.0 | CLI shows which chunks would go to the LLM and why |
| P4 | LLM analysis | MVP | 10 | 28.0 | Guarded, schema-valid findings from real chunks; cost tracked |
| P5 | Merge, scoring, calibration | MVP | 11 | 35.5 | `skillissue scan owner/repo` prints a full report JSON; scores calibrated on 30 repos |
| P6 | API, queue, limits | MVP | 16 | 44.0 | curl a scan end to end with SSE progress, caching, and limits |
| P7 | Web app | MVP | 21 | 68.5 | Browser flow Home → progress → report → filter → detail works in light/dark |
| P8 | Hardening and reliability | MVP | 10 | 22.0 | Malicious-repo, leak, XSS, failure, and cost tests pass in CI |
| P9 | QA, accessibility, legal, deploy, launch | MVP | 11 | 28.0 | Live public URL with monitoring and legal pages |
| P10 | Fix suggestions | v1 | 6 | 15.5 | Suggest a fix, see a validated diff |
| P11 | Verification, share, badge, history | v1 | 11 | 34.5 | Verified/unverified labels, share card, badge, history |
| P12 | Trust upgrades | v1.5 | 6 | 26.0 | Tier-2 verification, Go support, calibration pass 2 |

**MVP total (P0–P9): 123 tasks, about 313.5 focused hours** (realistic: about 470 hours). This supersedes the rough range in `PRD.md` §22 if they differ.

## Suggested order and weekends

| Block | Do | Why first |
|---|---|---|
| Spikes (do before anything else, 1 evening) | S-1 through S-4 below | They de-risk the four things most likely to invalidate the plan |
| Weekend 1 | P0, P1 | Repo, tooling, acquisition, hygiene: a working CLI that already prints useful output |
| Weekend 2 | P2, P3 | Scanners + sandbox + sampling: the grounded core |
| Weekend 3 | P4, P5 | LLM stage + scoring: first real report from the CLI; calibrate |
| Weekend 4 | P6 | API and queue |
| Weekends 5–6 | P7 | Web app |
| Weekend 7 | P8, P9 | Harden, deploy, launch |

## Spikes (timeboxed, do first)

| ID | Question | Timebox | Output | Decides |
|---|---|---|---|---|
| S-1 | Can Semgrep run fully offline with baked rules in the scanner image, and are the rule licenses acceptable for a public service? | 2 h | Notes in `MEMORY.md`; working `docker run --network none` example | PRD Q4, ADR-011 |
| S-2 | Does rootless Docker work on the target VPS/OS with the required flags (read-only, tmpfs, caps dropped, pids/mem limits)? | 2 h | Working `docker run` transcript | Hosting choice (PRD Q2) |
| S-3 | Is the tarball extractor safe and fast enough (tar bomb, symlinks, traversal, 150 MB cap)? | 1.5 h | Prototype + 6 malicious fixtures passing | ADR-002 |
| S-4 | Does the sampling + triage prompt produce useful, low-noise findings on 5 real small repos with Haiku-class model? | 3 h | Precision notes; token/cost per repo | Model choice, prompt shape, cost target |

---

## P0 — Foundations

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-0.1 | Confirm stack defaults (PRD Q1) and record ADRs in `MEMORY.md` | 1 | S-1..S-4 | Decisions written with status Decided |
| [ ] | T-0.2 | Create GitHub repo and monorepo skeleton per `ARCHITECTURE.md` §6; add LICENSE, README stub, `.gitignore`, `.editorconfig`, docs folder | 1 | T-0.1 | Repo cloned, tree matches §6 |
| [ ] | T-0.3 | Tooling: API (uv or poetry, ruff, mypy strict, pytest, pytest-asyncio, hypothesis); web (pnpm, eslint, prettier, tsc strict, vitest); Makefile targets `dev test lint typecheck eval build` | 2 | T-0.2 | `make lint typecheck test` runs green on empty projects |
| [ ] | T-0.4 | docker-compose dev stack: postgres, redis, api, worker, web with hot reload | 2 | T-0.3 | `make dev` boots all services; `/healthz` returns 200 |
| [ ] | T-0.5 | Config system with pydantic-settings and `.env.example` listing every variable in `ARCHITECTURE.md` §17.2 | 1 | T-0.3 | App fails fast with clear error on missing required var |
| [ ] | T-0.6 | CI workflow: lint, typecheck, unit tests, with dependency caching | 1.5 | T-0.3 | CI green on main and on a PR |
| [ ] | T-0.7 | Alembic init and migration 0001 with the full DDL from `ARCHITECTURE.md` §8 | 2 | T-0.4 | `alembic upgrade head` and `downgrade base` both work on empty DB |
| [ ] | T-0.8 | structlog JSON logging, request-id middleware, RFC 9457 problem+json error handler | 1.5 | T-0.3 | Any raised `AppError` returns the documented shape with `request_id` |
| [ ] | T-0.9 | Pre-commit hooks: ruff, eslint, prettier, gitleaks | 0.5 | T-0.3 | Committing a fake key is blocked locally |
| [ ] | T-0.10 | Copy the six docs into `docs/`; add CONTRIBUTING.md and SECURITY.md stubs | 0.5 | T-0.2 | Files present and linked from README |
| [ ] | T-0.11 | Check name/domain/trademark availability (PRD Q3) and decide domain | 0.5 | none | Decision in `MEMORY.md` |
| [ ] | T-0.12 | FakeLLM scaffold and an `LLM_MODE` fake-vs-live switch | 1 | T-0.5 | Tests can inject recorded responses |

## P1 — Source acquisition and filtering

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [x] | T-1.1 | URL parser `domain/url.py` (regexes in `ARCHITECTURE.md` §7.1) with table-driven tests (at least 40 cases) and hypothesis properties | 2.5 | T-0.3 | Accepts all forms in PRD FR-1.1; rejects non-GitHub hosts, credentials, traversal, control chars; properties pass |
| [x] | T-1.2 | GitHub client: repo metadata, commit SHA resolve, ETag cache in Redis, error mapping, rate-limit header handling | 3 | T-0.5, T-1.1 | Maps 404/403/409/rate-limit to documented error codes; uses server token; ETag saves calls in a test |
| [ ] | T-1.3 | Tarball downloader: streaming to disk, 150 MB cap, redirect handling, timeouts, 1 retry | 2 | T-1.2 | Oversize stream aborts cleanly; partial files removed |
| [ ] | T-1.4 | Safe extractor with `filter="data"` plus own checks (paths, links skipped, entry/size/depth caps, permissions normalized) | 3 | T-1.3, S-3 | All malicious fixtures neutralized; no file outside dest; caps enforced |
| [ ] | T-1.5 | Hardened `git clone` fallback and tests (mocked) | 1.5 | T-1.3 | Flags per `ARCHITECTURE.md` §7.2; `.git` removed after clone |
| [ ] | T-1.6 | File walker and filters (dirs, lockfiles, minified, binary, size, lines, generated markers) | 2 | T-1.4 | Filter fixture repo yields expected included/excluded lists |
| [ ] | T-1.7 | Language detection, LOC counter, and manifest `files.json` (flags: test, config, entrypoint, risk score) | 2 | T-1.6 | LOC within ±5% of `cloc` on 3 sample repos |
| [ ] | T-1.8 | Coverage decision logic (`reduced_coverage`, `hygiene_only`, `partial`) | 1 | T-1.7 | Unit tests for each branch |
| [ ] | T-1.9 | Hygiene checks (all nine from `ARCHITECTURE.md` §7.5) | 3 | T-1.7 | Fixture repos produce expected flags; `.env.example` is not flagged |
| [ ] | T-1.10 | CLI `python -m skillissue.cli acquire owner/repo` printing manifest and hygiene flags | 1 | T-1.9 | Works on 3 real public repos |
| [ ] | T-1.11 | Denylist and `skillissue-optout` root-file check at acquisition | 1 | T-1.6 | Repo with the file is refused with `repo_opted_out` |

## P2 — Scanners and sandbox

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-2.1 | Scanner image Dockerfile: pinned semgrep, bandit, radon, lizard, node + eslint + plugins, gitleaks, osv-scanner; non-root user 10001 | 3 | S-1 | Image builds reproducibly; `--version` of each tool printed in a smoke test |
| [ ] | T-2.2 | Bake Semgrep rule packs at build time (offline) and record license notes | 2 | T-2.1, S-1 | Semgrep runs with `--network none` and finds a seeded issue |
| [ ] | T-2.3 | ESLint fixed flat config (security + correctness rules) and noisy-rule list; ignore repo configs | 2 | T-2.1 | Repo-supplied config with a malicious plugin is never loaded (test) |
| [ ] | T-2.4 | Bandit config file | 0.5 | T-2.1 | Seeded Python issue detected |
| [ ] | T-2.5 | gitleaks config with `--redact`; parse columns to build `secret_spans` | 2 | T-2.1 | Fake AWS-style key found; output has no full secret |
| [ ] | T-2.6 | OSV offline DB refresh job, volume, and offline scan invocation | 3 | T-2.1 | Known-vulnerable lockfile flagged with `--network none` |
| [ ] | T-2.7 | `scanner_runner` entrypoint: per-tool timeouts, status collection, output size caps | 3 | T-2.2..T-2.6 | One failing tool does not stop others; statuses recorded |
| [ ] | T-2.8 | Lizard (Python API) and Radon integration | 2 | T-2.7 | Complexity signals emitted with thresholds from `ARCHITECTURE.md` §7.4 |
| [ ] | T-2.9 | Normalizers per tool to `RawSignal` with severity/confidence maps; tests using recorded tool outputs | 6 | T-2.7 | Snapshot tests for each tool; mapping table implemented exactly |
| [ ] | T-2.10 | Snippet builder and secret masking (first 4 + last 2 chars) inside the container | 2 | T-2.5, T-2.9 | Property test: never more than 6 visible chars of any secret |
| [ ] | T-2.11 | Sandbox runner `sandbox/docker_runner.py`: flags, mounts, deadline kill, cleanup, output validation | 3 | T-2.7, S-2 | Command matches `ARCHITECTURE.md` §11.2; timeouts kill the container |
| [ ] | T-2.12 | Sandbox tests: no network, read-only FS, resource limits, non-root, leftover containers cleaned after crash | 3 | T-2.11 | Tests fail if any flag is removed |
| [ ] | T-2.13 | CI: build scanner image, Trivy scan, pin digest | 1.5 | T-2.1 | CI fails on high/critical image vulns |
| [ ] | T-2.14 | CLI `scan-local <dir>` writing `signals.json` | 1 | T-2.11 | Works on 3 repos in under 60 s each |

## P3 — Sampling and chunking

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [x] | T-3.1 | tree-sitter setup for Python, JavaScript, TypeScript; extract functions/classes/methods with line ranges | 3 | T-1.7 | Unit tests on fixture files; syntax-error files handled without crash |
| [x] | T-3.2 | Chunker: size targets, merge small, split large with 20-line overlap, absolute line-numbered rendering, context header | 4 | T-3.1 | Chunks within 2k–6k tokens (estimated); line numbers match source |
| [x] | T-3.3 | File scoring: formula, risk-path and entrypoint detectors, test/fixture detectors | 3 | T-2.14, T-1.7 | Ranked list for a fixture repo matches expected order |
| [x] | T-3.4 | Greedy selector with budgets, diversity constraints, forced inclusion of chunks holding medium+ signals | 3 | T-3.2, T-3.3 | Never exceeds 30 chunks or 150k tokens; diversity rules verified |
| [x] | T-3.5 | Token estimator and budget accounting utility | 1 | T-3.2 | Estimate within 15% of real tokenizer on 5 samples (measure with API count endpoint once) |
| [x] | T-3.6 | Secret redaction pass for chunk text; `.env`/key-file exclusion; long-literal truncation | 2 | T-2.5, T-3.2 | Test asserts fake secrets never appear in any chunk text |
| [x] | T-3.7 | CLI `sample <dir>` printing chosen chunks with reasons | 1 | T-3.4 | Output explains each selection |

## P4 — LLM analysis

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-4.1 | LLM adapter (Anthropic SDK async): model config, retries with backoff, timeouts | 3 | T-0.12 | 429/5xx retried twice; timeouts enforced; fake and live modes work |
| [ ] | T-4.2 | Tool schema `report_findings`, Pydantic models, and prompt file `analyze_v1.md` | 2 | T-4.1 | Schema matches `ARCHITECTURE.md` §7.8; forced tool choice works |
| [ ] | T-4.3 | Batch builder (≤ 3 chunks, ≤ 8k tokens), nonce tags, closing-tag neutralization | 2 | T-3.4 | Injection test: chunk containing a fake closing tag cannot break out |
| [ ] | T-4.4 | Guards: schema, signal ids, path, line range, snippet match, URL/HTML strip, roast blocklist | 5 | T-4.2 | Adversarial fixtures (hallucinated lines, wrong paths, oversized output) all dropped with counters |
| [ ] | T-4.5 | Prompt caching and `llm_cache` (hash keys, 30-day TTL) | 2 | T-4.1 | Second run on unchanged files makes zero LLM calls |
| [ ] | T-4.6 | Cost tracker: pricing table in config, per-scan cap, atomic daily ledger update | 3 | T-4.1, T-0.7 | Scan stops calling when cap hit; ledger correct under concurrency (test) |
| [ ] | T-4.7 | Concurrency controller (max 4), deadlines, partial results, `scanners_only` fallback | 3 | T-4.4, T-4.6 | LLM outage test yields a scanners-only report with banner flag |
| [ ] | T-4.8 | Prompt-injection fixtures and `injection_suspected` heuristic | 2 | T-4.4 | Injection README fixture does not alter findings |
| [ ] | T-4.9 | Recorded FakeLLM fixtures for golden/integration tests | 2 | T-4.2 | Fixtures stored under `tests/fixtures/llm/` |
| [ ] | T-4.10 | Prompt iteration on 10 repos; record precision notes and token/cost stats in `MEMORY.md` | 4 | T-4.7, S-4 | Mean cost per scan within the PRD target or a decision recorded |

## P5 — Merge, scoring, calibration

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-5.1 | Merge: signals to candidates, apply triage, add LLM-only findings, confidence policy (PRD §12.3) | 3 | T-2.9, T-4.7 | Table-driven tests for confirm/reject/uncertain/new |
| [ ] | T-5.2 | Overlap merge and fingerprints (`ARCHITECTURE.md` §7.9) | 2 | T-5.1 | Same issue from two tools becomes one finding with both sources |
| [ ] | T-5.3 | Ranking (`impact_rank`), visibility cap 50, hidden counts | 1 | T-5.2 | Tie-break order per PRD FR-4.4 |
| [ ] | T-5.4 | Scoring pure function with half-up rounding; tests including the PRD §11.7 example (= 18), monotonicity, floors, bounds | 3 | T-5.3 | All tests pass; property: adding a finding never lowers the score |
| [ ] | T-5.5 | File heat computation and `stats.files` | 1.5 | T-5.3 | Top 400 files stored; rest aggregated by directory |
| [ ] | T-5.6 | Summary sentence and tier copy constants shared between API and web | 1 | T-5.4 | Generated from `DESIGN.md` §12.4 templates |
| [ ] | T-5.7 | Orchestrator `run_scan` stage machine: checkpoints, events, deadlines, cancellation hooks, guaranteed cleanup | 6 | T-5.4, T-2.11, T-4.7 | Kill -9 mid-scan then resume works; work dir always removed |
| [ ] | T-5.8 | End-to-end CLI `skillissue scan owner/repo` printing report JSON | 2 | T-5.7 | Real repo produces a valid report matching the PRD sample shape |
| [ ] | T-5.9 | **Calibrate `k_c` and weights** on the 30-repo reference set: assemble and pin the set by SHA, hand-label at least 10 findings per repo, run the pipeline, compare score distribution to the PRD §11.7 target, adjust constants, bump `PIPELINE_VERSION`, record results | 10 | T-5.8, T-5.11 | Distribution within ±10 points of target per tier; results committed under `eval/results/` |
| [ ] | T-5.10 | Golden tests: 6–10 fixture repos with expected report JSON; CI gate of ±3 points unless version bumped | 2 | T-5.8 | Gate fails on an unintended score change |
| [ ] | T-5.11 | Eval harness `make eval`: precision at confidence ≥ 0.8, recall vs labels, cost per scan, latency | 4 | T-5.8 | Prints a summary table and writes JSON |

## P6 — API, queue, limits

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-6.1 | FastAPI app factory, routers, OpenAPI export committed, CORS, security headers | 2 | T-0.8 | `openapi.json` generated; CI fails on unreviewed diff |
| [ ] | T-6.2 | SQLAlchemy models and repositories | 3 | T-0.7 | CRUD tests pass |
| [ ] | T-6.3 | `POST /scans`: parse, denylist, GitHub resolve, cache/coalesce, limits, budget, enqueue (`ARCHITECTURE.md` §7.1) | 5 | T-6.2, T-1.2, T-6.8, T-6.9 | 202 new, 200 cached, coalescing verified with concurrent requests |
| [ ] | T-6.4 | `GET /scans/{id}`, `/report`, `/findings`, `/findings/{id}` with cursor pagination | 4 | T-6.2 | Response shapes match `ARCHITECTURE.md` §9 |
| [ ] | T-6.5 | RQ worker wiring, `run_scan` job, concurrency config, systemd unit and compose entry | 3 | T-5.7 | Worker processes 5 queued scans concurrently at limit 2 |
| [ ] | T-6.6 | Heartbeat, reaper, and janitor jobs (stuck scans, work dirs, expiry, signals TTL, stale containers) | 4 | T-6.5 | Killing the worker leads to `worker_lost` or re-enqueue as specified |
| [ ] | T-6.7 | SSE endpoint: Redis pub/sub, replay from `scan_events`, heartbeat comments, per-IP cap of 5 | 4 | T-6.5 | Reconnect with `Last-Event-ID` replays missed events |
| [ ] | T-6.8 | Redis sliding-window rate limiter, repo cooldown, IP hashing with monthly salt | 3 | T-0.5 | 4th scan in an hour denied with correct reset time |
| [ ] | T-6.9 | Budget ledger checks and `budget_exhausted` path | 1.5 | T-4.6 | New non-cached scans blocked; cached still served |
| [ ] | T-6.10 | Turnstile verification behind a flag | 1.5 | T-6.3 | With flag on, missing token returns 403 |
| [ ] | T-6.11 | Feedback endpoint and rate limit | 1 | T-6.2, T-6.8 | Duplicate feedback per IP/kind ignored |
| [ ] | T-6.12 | Admin endpoints, token auth, audit log | 2.5 | T-6.2 | Every admin call appears in `admin_audit` |
| [ ] | T-6.13 | `/healthz`, `/readyz`, `/metrics` | 1.5 | T-6.1 | Readiness fails when Docker socket unreachable |
| [ ] | T-6.14 | Integration tests: create, cache, coalesce, limits, budget, SSE, cancel, reaper | 5 | T-6.3..T-6.9 | All pass in CI with FakeLLM |
| [ ] | T-6.15 | Contract tests with schemathesis | 1.5 | T-6.1 | No 5xx under fuzzing |
| [ ] | T-6.16 | Cancel endpoint (`POST /scans/{id}/cancel`) and orchestrator hook test | 1.5 | T-5.7, T-6.5 | Running container killed within 5 s |

## P7 — Web app

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-7.1 | Next.js setup, `next/font`, `tokens.json` to CSS variables and Tailwind theme, flash-free theme toggle | 3 | T-0.3 | Light/dark switch without flash; tokens match `DESIGN.md` §14 |
| [ ] | T-7.2 | Layout, header/footer, container, skip link, messages catalog (`en.json`) | 2 | T-7.1 | No inline UI strings outside the catalog (lint rule) |
| [ ] | T-7.3 | Token contrast script: recompute every pair in `DESIGN.md` §4.3 and fail CI below thresholds | 1.5 | T-7.1 | Script prints the table and exits non-zero on regression |
| [ ] | T-7.4 | Font verification on real renders: Bricolage width axis at small sizes, tabular numerals availability; decide numeric column font (DQ1, DQ2) | 1.5 | T-7.1 | Decision recorded in `DESIGN.md` §14.5 and `MEMORY.md` |
| [ ] | T-7.5 | API client (`openapi-typescript`), TanStack Query hooks, error-code to message mapper | 2.5 | T-6.1 | Types compile against generated spec |
| [ ] | T-7.6 | Home: hero, URL form with validation and normalization, example chips, idle probe | 5 | T-7.2, T-7.7, T-7.5 | Pasting each accepted URL form submits correctly; invalid shows inline error without network |
| [ ] | T-7.7 | Probe component (SVG): modes idle/measuring/result/skeleton, meter semantics, unit tests | 4 | T-7.1 | Renders all tiers; `aria-valuetext` correct |
| [ ] | T-7.8 | Scan page: stage list, SSE client with polling fallback, error states, cancel button (enabled when T-6.16 done) | 5 | T-7.5, T-6.7 | Works with SSE blocked (polling) and after reload mid-scan |
| [ ] | T-7.9 | "The reading" animation with reduced-motion path | 2 | T-7.7 | Plays once on fresh completion; skipped on revisit and reduced motion |
| [ ] | T-7.10 | Report header: tier chip, score, summary sentence, banners (coverage, tool warnings, scanners-only) | 3 | T-7.5, T-7.7 | All banner states covered by component tests |
| [ ] | T-7.11 | Subscore list (`dl`, 12-step bars, click to filter) | 2 | T-7.10 | Bars are `aria-hidden`; numbers and counts readable |
| [ ] | T-7.12 | HeatMap (`d3-hierarchy` squarified), HeatList, Map/List toggle, tooltips, keyboard support | 6 | T-7.10 | Tile click filters findings; list view is fully equivalent |
| [ ] | T-7.13 | FilterBar with URL params, removable chips, live result count | 4 | T-7.11 | Reload preserves filters; count announced politely |
| [ ] | T-7.14 | FindingList (keyboard navigation), FindingRow, SeverityIndicator, ConfidenceLabel | 4 | T-7.13 | Arrow keys move selection; glyph plus word always shown |
| [ ] | T-7.15 | FindingDetail panel and mobile bottom sheet; CodeSnippet with mask notice and copy; evidence links; feedback row | 6 | T-7.14 | Secret snippets show masked text and the rotate notice first |
| [ ] | T-7.16 | CalcPopover/dialog showing this scan's inputs and floors applied | 3 | T-7.10 | Numbers reproduce the overall score by hand |
| [ ] | T-7.17 | Static pages: how scoring works, about, privacy, opt-out, 404, error boundary | 3 | T-7.2 | Content reviewed against `DESIGN.md` §12.7 |
| [ ] | T-7.18 | SSR report route `/r/[owner]/[repo]`, meta tags, `noindex` default, revalidate 60 s | 2.5 | T-7.10 | View-source shows score and tier without JS |
| [ ] | T-7.19 | Dark theme pass across all components | 2 | T-7.15 | Contrast script and manual check pass |
| [ ] | T-7.20 | Playwright e2e (home to report), axe checks, visual snapshots for five tiers in both themes | 5 | T-7.15 | CI runs it; zero axe violations on core routes |
| [ ] | T-7.21 | Plausible events per PRD §19.1 (no repo names) | 1.5 | T-7.8 | Events visible in dashboard; no PII |

## P8 — Hardening and reliability

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-8.1 | Threat-model review against `ARCHITECTURE.md` §15; fix gaps; record results | 2 | P6 | Checklist in `docs/security-review.md` signed off |
| [ ] | T-8.2 | Malicious-repo fixture suite in CI (tar bombs, symlinks, traversal, huge files, injection README) | 3 | T-1.4, T-2.12 | Suite fails if any limit is removed |
| [ ] | T-8.3 | Secret-leak tests: fake keys through the whole pipeline; assert absent from DB, logs, LLM payload snapshots, report JSON, share card | 3 | T-5.8, T-6.4 | Zero occurrences of full fake secrets |
| [ ] | T-8.4 | XSS tests: payload corpus in titles, explanations, file paths, snippets rendered by the web app | 2 | T-7.15 | No script execution; markdown sanitizer allowlist enforced |
| [ ] | T-8.5 | Load tests (k6): cached report GETs, SSE with 200 clients, queued scans; tune limits | 2 | T-6.14 | Targets in PRD NFR-P2/P3 met on the target host |
| [ ] | T-8.6 | Failure injection: LLM down, Redis down, scanner crash, worker kill, disk full | 3 | T-6.14 | Behavior matches `ARCHITECTURE.md` §20 |
| [ ] | T-8.7 | Cost tests: budget stop, per-scan cap, cache hit costs zero | 1.5 | T-4.6, T-6.9 | Tests green |
| [ ] | T-8.8 | Postgres backups and a tested restore | 1.5 | T-9.1 | Restore drill documented |
| [ ] | T-8.9 | Dependency and image scanning in CI; Renovate or Dependabot | 1 | T-0.6 | PRs opened automatically for updates |
| [ ] | T-8.10 | Observability: Prometheus metrics, alerts, Sentry, runbooks in `ops/runbooks/` | 3 | T-6.13 | Each alert in `ARCHITECTURE.md` §16 has a runbook |

## P9 — QA, accessibility, legal, deploy, launch

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-9.1 | Provision VPS: rootless Docker, worker systemd unit, firewall egress allowlist, work-dir disk quota | 4 | S-2 | `readyz` green; egress restricted as specified |
| [ ] | T-9.2 | Deploy API, worker, Redis, Postgres with compose behind Caddy TLS; deploy web on Vercel; set secrets | 3 | T-9.1 | Public URL serves the app end to end |
| [ ] | T-9.3 | CD pipeline with migrations and smoke test | 2 | T-9.2 | Push to main deploys; failing smoke test rolls back |
| [ ] | T-9.4 | Manual accessibility: keyboard walkthrough, 200% zoom, reflow at 320 px, contrast spot checks | 2 | T-7.20 | Issues logged and fixed |
| [ ] | T-9.5 | Screen reader pass (VoiceOver and NVDA): meter, list, heat map alternative, live regions; fix findings | 3 | T-9.4 | Checklist in `DESIGN.md` §14.4 ticked |
| [ ] | T-9.6 | Final legal pages; end-to-end opt-out test; license audit of scanners and rules (PRD Q4) | 3 | T-7.17 | Audit result recorded in `MEMORY.md` |
| [ ] | T-9.7 | Choose three example repos including an owner-made messy demo containing obviously fake secrets | 1 | T-5.8 | Examples produce Raw/Lightly toasted, Cooked/Burnt, and mixed results |
| [ ] | T-9.8 | About page with owner info; README with architecture diagram, metrics, and demo GIF | 3 | T-9.2 | README shows measured precision, cost, and latency numbers |
| [ ] | T-9.9 | Private beta with about 10 people; collect feedback; fix top issues | 4 | T-9.3 | Top 5 issues closed |
| [ ] | T-9.10 | Launch checklist: domain, robots/noindex decision (PRD Q6), monitoring, budget cap, rollback plan | 1.5 | T-9.9 | Checklist complete |
| [ ] | T-9.11 | Public launch post and share assets | 1.5 | T-9.10 | Post published |

## P10 — v1: Fix suggestions

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-10.1 | `propose_fix` tool schema, prompt, and `LLM_FIX_MODEL` config | 2 | MVP | Returns explanation, diff, files touched |
| [ ] | T-10.2 | Eligibility rules and `POST /findings/{id}/fix` with rate limit (10 per hour per IP) | 2 | T-10.1 | Ineligible findings rejected with clear code |
| [ ] | T-10.3 | Patch validation: `git apply --check` in scratch, limits (3 files, 60 lines), dangerous-addition checks | 3 | T-10.1 | Bad diffs rejected with reasons |
| [ ] | T-10.4 | Fix persistence and `GET /fixes/{id}` | 1.5 | T-10.2 | Idempotent: second request returns existing fix |
| [ ] | T-10.5 | UI: Suggest a fix, diff viewer, copy and download patch | 5 | T-10.4 | Works on desktop and mobile |
| [ ] | T-10.6 | Adversarial fix tests: traversal in diff headers, huge diffs, binary patches, lockfile edits | 2 | T-10.3 | All rejected |

## P11 — v1: Verification, share, badge, history

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-11.1 | Verification runner: apply patch in scratch; parse check for Python, JS, TS | 3 | T-10.3 | Broken patches labeled `failed` |
| [ ] | T-11.2 | Re-run the originating tool/rule on touched files inside the scanner container | 4 | T-11.1 | Before/after counts stored |
| [ ] | T-11.3 | Decision logic with label semantics enforced in code (LLM-only findings can never be `verified`) | 3 | T-11.2 | Unit tests including regression cases |
| [ ] | T-11.4 | Evidence storage and UI pill with fixed explanation strings | 3 | T-11.3 | Strings match `DESIGN.md` §7.6 |
| [ ] | T-11.5 | Share card route (`next/og`), fonts, five tiers in both card variants, snapshot tests | 4 | MVP | Renders under 1.5 s; long names truncated |
| [ ] | T-11.6 | Badge SVG endpoint, width calculation, cache headers | 2.5 | MVP | Renders in GitHub README preview |
| [ ] | T-11.7 | Share dialog (link, card, badge) | 3 | T-11.5, T-11.6 | Focus trap and Esc work |
| [ ] | T-11.8 | History endpoint, diff-by-fingerprint, UI chart and table with data-table alternative | 5 | MVP | Fixed/new/still-open groups correct on fixture history |
| [ ] | T-11.9 | Roast level toggle (options, `options_hash`, prompts, templates) | 2 | MVP | Score identical across roast levels (test) |
| [ ] | T-11.10 | Turnstile enforced by default and auto-enable on abuse threshold | 1 | T-6.10 | Flag flips automatically in a simulated burst |
| [ ] | T-11.11 | Fix eval: 40 findings, measure verified rate and audit false "verified" labels | 4 | T-11.4 | False "verified" count is 0 |

## P12 — v1.5: Trust upgrades

| Status | ID | Task | Est | Deps | Done when |
|---|---|---|---|---|---|
| [ ] | T-12.1 | ADR for Tier-2 sandbox: two-phase install or microVM | 3 | P11 | Decision recorded |
| [ ] | T-12.2 | Per-language runner images (Python, Node) | 4 | T-12.1 | Images pass sandbox tests |
| [ ] | T-12.3 | Baseline vs after runs of lint, typecheck, tests; exclude baseline failures | 6 | T-12.2 | Regression detected in a seeded fixture |
| [ ] | T-12.4 | Go support (Semgrep, Lizard, OSV) | 5 | P11 | Fixture Go repo scores sensibly |
| [ ] | T-12.5 | Calibration pass 2 on at least 50 repos | 6 | T-12.4 | New `k_c` documented; version bumped |
| [ ] | T-12.6 | Tier-2 verification UI copy and states | 2 | T-12.3 | Strings added to catalog and design doc |

---

## Backlog (v2 and later; do not start before MVP is live)

- GitHub OAuth/App for private repos; encrypted temp storage and immediate purge
- PR comments / Check Runs via GitHub Action or App
- Scan history per user, trend charts, repo comparison, opt-in leaderboard
- Tier-3 verification (LLM-written regression tests)
- More languages (Java, Rust, PHP), self-host image, VS Code extension
- Self-serve report removal for verified owners
- Translation catalogs

## Risk watch (review weekly)

| Risk | Signal | Response |
|---|---|---|
| Scope creep | Any task started that is not in the current phase | Stop; log in `MEMORY.md`; move to backlog |
| False positives | Precision at confidence ≥ 0.8 below 70% in eval | Tighten prompts and guards before adding features |
| Cost | Mean cost per scan above US$0.10 | Reduce chunk cap, tune sampling, cache more |
| Motivation | A phase takes over 2x its estimate | Cut the cut-list items below and ship a smaller MVP |

## Cut list (drop in this order if time runs short; each stays in TASK.md marked `[-]`)

1. T-7.21 analytics
2. T-7.16 calc popover (link to static page instead)
3. T-8.5 load tests
4. T-7.12 treemap (ship list view only)
5. T-6.10 Turnstile (rely on rate limits and budget)
6. T-2.8 Lizard/Radon complexity signals
