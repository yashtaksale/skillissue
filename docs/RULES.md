# SkillIssue — Rules

| Field | Value |
|---|---|
| Document version | 0.1 (draft) |
| Date | 2026-09-22 |
| Purpose | Non-negotiable rules for anyone (human or AI assistant) working on this codebase |
| Companion docs | `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `MEMORY.md`, `TASK.md` |

> Conventions: **MUST** = will be rejected in review / blocked by CI if violated. **MUST NOT** = same, inverted. **SHOULD** = strong default; deviation needs a comment explaining why and, if it's a real pattern change, an ADR in `ARCHITECTURE.md` §22. Numbers here restate `PRD.md`/`ARCHITECTURE.md` values for convenience; if they ever disagree, the source doc wins and this file should be corrected.

---

## 1. Precedence and scope

1. These rules apply to every change in the `skillissue` monorepo: application code, infra, docs, CI, prompts.
2. If a rule here conflicts with `PRD.md` or `ARCHITECTURE.md`, treat it as a bug in this file — fix the conflict before proceeding, don't silently pick one.
3. If you (human or AI assistant) are about to do something these rules don't cover, default to the **most cautious** reading of §3 (Trust boundaries) and §4 (Security) before optimizing for speed or cleverness.

---

## 2. The five rules that matter most

If you remember nothing else from this document, remember these. Everything below is elaboration.

1. **Never execute code from a scanned repository.** Not in MVP, not "just to check something," not in a debugger, not in a notebook. Parsing is fine (in a sandbox); running is not, until Tier-2 verification (v1.5) is built with its own explicit sandboxing.
2. **A finding is never labeled "verified" without machine-checked evidence.** LLM-only findings are `unverified`, always. This is enforced in code (a type-level distinction, not a string you can typo past), not just by convention.
3. **Full secret values never leave the scanner container, and never get logged, stored, or sent to the LLM.** Masking happens at the earliest possible point.
4. **The score is a pure, deterministic function of stored findings.** No LLM call is ever in the scoring path. Given the same findings, the same code, always the same score.
5. **Don't build past the current phase in `TASK.md`.** If you notice yourself adding a feature not in the current phase, stop, and either log it in `MEMORY.md` §6 (parking lot) or add it to the correct phase — don't just build it because it's easy right now.

---

## 3. Trust boundaries (restated from `ARCHITECTURE.md` §4 — read that first)

There are exactly five trust boundaries in this system. Every rule below exists to defend one of them.

1. Internet → Web/API — **untrusted user input.**
2. API/Worker → GitHub/Anthropic — third-party services; only our secrets cross this boundary, never repo content credentials.
3. Worker → Scanner container — **the big one: untrusted repository content.**
4. Repo content → LLM prompt — untrusted text inside a trusted prompt structure.
5. LLM output → Worker/DB/UI — **untrusted model output**, even though the model is "ours."

**Rule:** any code that touches data crossing one of these boundaries MUST be identifiable by reading its module path or a comment referencing this section. Don't bury boundary-crossing logic inside an unrelated helper.

---

## 4. Security rules (hard requirements)

### 4.1 Untrusted repository content
- MUST extract archives with the safe extractor only (`pipeline/acquire.py`); MUST NOT call `tarfile.extractall()` or `git clone` directly anywhere else in the codebase.
- MUST NOT follow, create, or extract symlinks or hardlinks from a scanned repo, ever.
- MUST enforce every limit in `PRD.md` §14 (repo size, file count, file size, line count, entries, depth) at the point of extraction/walking, not just "eventually" downstream.
- MUST run all scanning/parsing of repo content inside the hardened container (`ARCHITECTURE.md` §11.2 flags exactly). MUST NOT add a "quick local dev shortcut" that runs Semgrep/ESLint/etc. directly on the host against real (non-fixture) repo content — fixtures under `tests/fixtures/` are fine to run locally since they're ours.
- MUST NOT mount the Docker socket into any container that processes repository content.
- MUST NOT add a code path, feature flag, or debug mode that executes a scanned repo's code, install scripts, or build steps in MVP or v1. This changes only in v1.5 under the explicit design in `ARCHITECTURE.md` §7.12 Tier-2, and only with network-restricted installs.
- New scanner tool integrations MUST go through the same container and MUST be added to the sandbox test suite (`T-2.12`-style tests: no network, read-only FS, resource limits, cleanup) before merging.

### 4.2 Secrets (both the app's own, and secrets found in scanned repos)
- MUST mask secrets found by gitleaks (or any tool) at the point of detection, inside the container, before the signal ever leaves it. Masking = first 4 + last 2 characters visible, rest replaced with `•`.
- MUST NOT log a request/response body that could contain repo content or LLM prompts/completions in full. Log sizes, hashes, and counts instead.
- MUST NOT send `.env*` files or files with ≥ 5 gitleaks matches to the LLM at all (not even redacted).
- MUST NOT call any third-party API to "validate" whether a found secret is live (e.g., pinging AWS with a found key). Ever.
- The application's own secrets (Anthropic key, GitHub token, DB/Redis URLs, admin token) MUST come from environment/secrets manager, MUST NOT be committed, and MUST NOT be logged. `.env.example` lists names only, never real values.
- The GitHub token used by the server MUST be scope-less / public-read-only. MUST NOT use a token with private repo access in MVP or v1.
- Every new code path that touches secret material (app secrets or repo secrets) MUST have a test asserting the secret does not leak into logs, DB rows, LLM payloads, or API responses.

### 4.3 LLM input/output
- All repository content sent to the LLM MUST go through the redaction pass (secret masking, `.env` exclusion, literal truncation) — no new call site may bypass `llm/client.py`'s batch builder.
- MUST use forced tool-use (`tool_choice`) for every structured extraction call. MUST NOT parse free-text LLM output with regex/eval as a primary mechanism.
- Every field returned by the LLM that will be rendered to a user (title, explanation, roast, fix explanation) MUST be escaped/sanitized before rendering. MUST NOT use `dangerouslySetInnerHTML` (or equivalent) on LLM-derived text without going through the sanitizer allowlist.
- Every finding derived from LLM output MUST pass the grounding guards (`ARCHITECTURE.md` §7.8: known signal id, file in batch, line range in bounds, snippet match) before being persisted. MUST NOT add a path that persists an LLM finding without running it through `llm/guards.py`.
- MUST NOT give the LLM any tool that has a side effect (no web access, no file write, no exec) in this application. Its only tool is the structured-output schema.
- Treat repo content in prompts as data, not instructions, in both the system prompt and in code comments explaining the call site. If you're ever tempted to let the model "decide" something based on instructions found in repo content, that's the bug this rule exists to prevent.

### 4.4 Scoring integrity
- The scoring function (`domain/scoring.py`) MUST be pure: no network calls, no DB calls, no LLM calls, no wall-clock reads (`now()`) inside it. Given the same `(findings, loc, hygiene_flags, has_live_secret)` input, it MUST return the same output, always.
- Any change to weights, `k_c` constants, severity weights, or the formula shape MUST bump `pipeline_version` (major segment) per `PRD.md` §11.8, and MUST update the golden tests.
- MUST NOT let display-layer truncation (top 50 shown) affect the score — scoring always runs over all findings with confidence ≥ 0.5, not just the visible ones.
- MUST persist `score_inputs` on every scan so the score is reproducible offline without re-running the pipeline.

### 4.5 Verification labels (v1+)
- The four verification states (`verified`, `unverified`, `failed`, `not_run`) MUST be an enum, not a free string, at every layer (DB, API, UI).
- A finding with no tool-backed signal (LLM-only) MUST be structurally prevented from reaching `verified` — this MUST be enforced in the verification decision function itself (e.g., it should be impossible to construct a `verified` result for a finding whose `rule_sources` doesn't include a tool), not just filtered in the UI.
- Every `verified` result MUST carry evidence (commands run, exit codes, before/after counts) persisted alongside it. A `verified` label with no evidence is a bug, not a display issue.
- MUST NOT auto-apply, auto-commit, or push any fix to a user's GitHub repo, in any release covered by this document (MVP through v1.5). Fixes are copy/download only.

### 4.6 Abuse, cost, and denial of service
- Every endpoint that triggers non-cached work (scan creation, fix generation) MUST be behind rate limiting and MUST check the budget ledger before proceeding.
- MUST check the daily budget cap before every individual LLM call within a scan, not just once at scan start — a long scan MUST be able to stop mid-way if the cap is hit.
- MUST NOT remove or loosen a documented limit (`PRD.md` §14) without updating that table and explaining why in `MEMORY.md`.
- New endpoints that accept a URL, path, or identifier from the user MUST validate it against an explicit allowlist pattern (see §5.4) — MUST NOT construct outbound requests from raw user input (SSRF surface).

---

## 5. Engineering rules

### 5.1 General
- Python: `ruff` clean, `mypy --strict` clean, formatted with `ruff format`. TypeScript: `tsc --noEmit` clean, `eslint` clean, `prettier` formatted. No `# type: ignore` / `@ts-ignore` without a comment explaining why and a linked issue if it's not permanent.
- Public functions in `domain/`, `pipeline/`, and `llm/guards.py` MUST have type hints and a docstring stating pre/post-conditions where they're not obvious.
- No bare `except:` (Python) or empty `catch {}` (TypeScript) that swallows an error silently. If an error is genuinely ignorable, catch the specific type and comment why.
- Prefer small, pure functions in `domain/` over methods with hidden I/O. If a function in `domain/` needs to make a network or DB call, it's in the wrong directory.
- No global mutable state. Configuration flows through `pydantic-settings` (API/worker) or typed config modules (web), not module-level variables set at import time.

### 5.2 Testing
- New logic in `domain/` (scoring, fingerprinting, URL parsing, severity/confidence mapping) MUST ship with unit tests in the same PR. Coverage target for these modules is ≥ 80% (`PRD.md` NFR-M1).
- A bug fix MUST include a regression test that fails before the fix and passes after, except for pure copy/typo fixes.
- Any change to a scanner normalizer, the sampling formula, the LLM prompt, or the scoring formula MUST be checked against the golden test suite (`TASK.md` T-5.10) before merging; if scores intentionally change, `pipeline_version` is bumped and the golden fixtures are updated in the same PR.
- New guard logic (`llm/guards.py`) MUST include at least one adversarial fixture (the specific failure mode it's meant to catch), not just a happy-path test.
- Sandbox-related changes (Dockerfile, runner flags, extraction limits) MUST be validated against the malicious-fixture suite (`TASK.md` T-8.2) before merging.

### 5.3 API and data
- API responses MUST match the committed OpenAPI spec (`apps/api/openapi.json`); CI fails on an unreviewed diff, which means: regenerate the spec, review the diff, commit it deliberately — don't silently let CI auto-fix it.
- Every new DB migration MUST be forward-compatible with the currently-deployed app version (expand/contract pattern per `ARCHITECTURE.md` §17.4) — MUST NOT ship a migration that breaks the app running just before it deploys.
- New tables/columns holding user-facing content (findings, fixes, feedback) MUST consider the retention rules in `PRD.md` §14 — add to the janitor's cleanup logic if they need expiry, don't leave orphaned data.
- IP addresses MUST be hashed (HMAC + monthly-rotating salt) before persisting; MUST NOT persist raw IPs anywhere, including logs, beyond what the reverse proxy naturally retains outside our control.

### 5.4 Input validation (SSRF / injection surface)
- The GitHub URL parser (`domain/url.py`) is the **only** place that turns user input into a `(owner, repo, ref)` tuple. MUST NOT add a second parser elsewhere "for convenience."
- Every outbound HTTP request the server makes MUST be to a URL the server itself constructed from validated, typed fields (owner/repo/sha) — MUST NOT pass a user-supplied URL string directly to an HTTP client.
- Admin/internal endpoints MUST require the admin bearer token and MUST log to `admin_audit`; MUST NOT be reachable without auth even "temporarily during development" on a deployed environment.

### 5.5 Cost and models
- Model IDs, prices, and token/cost caps live in config (`ARCHITECTURE.md` §17.2), never hardcoded in a call site. Before wiring up a new model, verify its current model ID and pricing against Anthropic's documentation — MUST NOT rely on a remembered model name or price, since these change.
- Every LLM call site MUST record `tokens_in`, `tokens_out`, and computed cost against the scan and the daily ledger. A new call site that skips this is a bug.
- Prefer the cheaper/faster model for high-volume triage work and reserve the stronger model for low-volume, high-value work (fix generation). Don't upgrade the triage model "for quality" without measuring the cost delta and precision delta together (use `make eval`).

### 5.6 Frontend / design system discipline
- All colors, spacing, radii, and type sizes come from `apps/web/src/design/tokens.json` → CSS variables / Tailwind theme. MUST NOT hardcode a hex value, pixel spacing, or font size in a component — if the token you need doesn't exist, add it to `tokens.json` and to `DESIGN.md` §4/§5, don't inline it.
- Heat colors (`--heat-*`) are reserved for tier/severity/heat-map/badge/share-card use. MUST NOT use a heat color for a button, link, or section background — see `DESIGN.md` §4.5.
- Any UI element that conveys meaning through a heat color MUST also convey it through text (tier/severity word) and, where space allows, a glyph. A code reviewer should be able to grep for a new heat-colored element and find the accompanying text label right next to it.
- Toasted/Medium-Well fills MUST have the 1.5 px ink outline (`DESIGN.md` §4.3) — this is a contrast-failure workaround, not a style choice, and MUST NOT be dropped even if it "looks better" without it.
- All UI strings MUST come from the message catalog (`apps/web/src/messages/en.json`), not inline JSX text — this is enforced by lint rule (`TASK.md` T-7.2) and exists so the copy in `DESIGN.md` §12 stays the single source of truth and so translation is possible later.
- New interactive components MUST be keyboard-operable and MUST pass axe with zero violations before merging (`TASK.md` T-7.20 sets up the CI check; new components ride on it).
- Motion: no new component may add an animation outside what `DESIGN.md` §9 specifies without updating that section first. Default to no animation; the bar for adding one is "does this convey real state change," not "does this look nice."

### 5.7 Copy and tone
- Error messages MUST match `PRD.md` §15 / `DESIGN.md` §12.5 verbatim (or be added there first, then implemented) — don't improvise new error copy at the call site.
- New roast content (templates or LLM-generated) MUST pass the hard rules in `PRD.md` §17.3: never about the person, never diluting urgency on real secrets, always action-first for security findings. If you're unsure whether a roast line crosses the line, it does — cut it.
- No exclamation marks in system-generated copy (errors, banners, confirmations). This is a deliberate, checkable style rule, not a suggestion.

---

## 6. Process rules

### 6.1 Scope discipline
- Work happens in `TASK.md` phase order. MUST NOT start a v1/v1.5/v2 task while MVP (P0–P9) is incomplete, except spikes explicitly marked to run early.
- If a task turns out to need something from a later phase, either pull that specific piece forward **and add a task for it** in `TASK.md`, or descope the current task — don't silently build ahead.
- New feature ideas that come up mid-work go in `MEMORY.md` §6 (parking lot) or as a new `TASK.md` backlog item, not directly into the current PR.

### 6.2 Documentation as source of truth
- `PRD.md` = what and why. `ARCHITECTURE.md` = how. `DESIGN.md` = what it looks/sounds like. `TASK.md` = what's left and in what order. `MEMORY.md` = what happened and why we chose what we chose. `RULES.md` (this file) = what you're not allowed to do.
- Any change to a number, limit, endpoint shape, DB column, scoring constant, or user-facing string that appears in one of these docs MUST update that doc in the same PR. A PR that changes behavior without updating the doc that describes it is incomplete.
- Every work session MUST end with an update to `MEMORY.md` §1 (status snapshot) and, if anything decision-worthy happened, §2 (decisions) or §4 (running log). This is not optional busywork — it's what makes it possible to pick the project back up after a gap.

### 6.3 Reviewing your own work (solo project checklist)
Since this is a solo side project, "review" means you, later, or an AI assistant, checking the diff against this file before merging. Before merging any PR, check:
1. Does it stay within the current `TASK.md` phase?
2. Does it cross a trust boundary (§3)? If yes, does it follow the matching rules in §4?
3. Did it change a number/format/string that's documented elsewhere? Did the doc get updated?
4. Are there tests for new `domain/`, `llm/guards.py`, or `pipeline/` logic?
5. Did `MEMORY.md` get updated?

### 6.4 When an AI coding assistant is doing the work
- The assistant MUST read `RULES.md`, the relevant section(s) of `ARCHITECTURE.md`, and the current `TASK.md` phase before writing code for a task — not just the task's one-line description.
- The assistant MUST NOT "helpfully" implement a later-phase feature, a convenience shortcut that bypasses the sandbox, or a broader refactor than asked, without flagging it first.
- The assistant MUST flag, rather than silently work around, any case where following these rules would make a task significantly harder or slower — that's a signal the plan needs revisiting, not a reason to cut a corner quietly.
- The assistant MUST update `MEMORY.md` at natural checkpoints (end of a task, not just end of a session), since sessions with an AI assistant may be shorter and more frequent than solo human sessions.

---

## 7. Things you're never allowed to do (quick reference)

A condensed list for scanning. Full context is in the sections above — read them, don't just grep this list.

- Execute a scanned repo's code, install scripts, or build steps (MVP/v1).
- Label an LLM-only finding `verified`.
- Store, log, or send to the LLM a full unmasked secret from a scanned repo.
- Call the LLM from inside the scoring function, or make scoring depend on anything but stored findings + LOC + hygiene flags.
- Mount the Docker socket into a container that touches repo content.
- Parse free-text LLM output as the primary extraction mechanism (must use forced tool-use).
- Persist an LLM finding that hasn't passed the grounding guards.
- Auto-commit, auto-apply, or push a generated fix to a user's repo.
- Hardcode a color, spacing value, or font size in a frontend component instead of using a token.
- Use a heat color to convey meaning without an accompanying text label.
- Write inline UI copy outside the message catalog.
- Skip a rate-limit or budget check on a new cost-incurring endpoint.
- Start a v1/v1.5/v2 task before the MVP is live, without an explicit, logged decision to do so.
- End a work session without updating `MEMORY.md`.
