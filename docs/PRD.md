# SkillIssue — Product Requirements Document (PRD)

| Field | Value |
|---|---|
| Document version | 0.1 (draft) |
| Date | 2026-09-22 |
| Owner | Solo developer (side project) |
| Status | Draft, ready to build MVP |
| Companion docs | `ARCHITECTURE.md`, `DESIGN.md`, `MEMORY.md`, `TASK.md`, `RULES.md` |

> Conventions in this document: **MUST / SHOULD / MAY** follow RFC 2119. Requirement IDs (`FR-*`, `NFR-*`, `US-*`) are stable and referenced from `TASK.md`. Where a number appears (limits, weights), it is the **canonical value**; other docs copy it, this doc wins on conflict.

---

## 1. Summary

**SkillIssue** is a web app where you paste a public GitHub repository URL and get back a **"cooked score"** (0–100, higher = worse) plus a ranked list of real problems in the code: bugs, security issues, performance issues, maintainability issues, and repo hygiene gaps. Each problem is explained in plain language, located to a file and line, and (from v1) comes with a suggested fix that is **verified where verification is technically possible** and honestly labeled where it is not.

**One-liner:** *How cooked is your code?*

**Elevator pitch:** Paste a repo, get a roast you can actually learn from. Deterministic scanners find the problems; an LLM triages, explains, and proposes fixes; a transparent scoring rubric turns it into a number and a tier you can share.

**What it is not:** an enterprise SAST replacement, a code-review bot for private company repos (in MVP), or an "AI that fixes your whole codebase."

---

## 2. Background and problem statement

### 2.1 The problem
1. Developers, especially students, indie hackers, and people shipping AI-generated ("vibe-coded") apps, ship code with security holes, obvious bugs, hardcoded secrets, and missing basics (no tests, no CI, no license) and **never find out**.
2. Existing tools (Snyk, SonarQube, Semgrep, CodeQL, CodeRabbit, DeepSource, Codacy) are powerful but are aimed at teams: they need setup, accounts, CI wiring, and produce intimidating dashboards. A hobbyist will not set them up for a weekend project.
3. LLM-only "review my code" prompts produce confident-sounding but unreliable output: hallucinated line numbers, invented vulnerabilities, no grounding.

### 2.2 The opportunity
A zero-setup, zero-login, **paste-a-URL** experience that:
- Grounds LLM analysis in deterministic static-analysis signals (fewer hallucinations).
- Presents results as an entertaining, shareable **score** (growth loop) without sacrificing substance.
- Is honest about what is verified vs. merely suggested (trust differentiator).

### 2.3 Why now
AI coding tools have massively increased the volume of unreviewed code from people who do not know what to look for. That audience is large, online, meme-literate, and likes sharing scores.

---

## 3. Vision, goals, non-goals

### 3.1 Vision
The default "sanity check" a developer runs on a repo before showing it to the world, and the default thing they screenshot when it goes badly.

### 3.2 Goals (MVP → v1)
| ID | Goal | Measure |
|---|---|---|
| G1 | Zero-friction scan: URL in, report out, no signup | ≥ 70% of URL submissions reach a completed report |
| G2 | Findings people trust | ≥ 70% precision on findings with confidence ≥ 0.8 (manual audit on 30 reference repos) |
| G3 | Fun and shareable | ≥ 15% of completed scans trigger a share/copy-link/badge action |
| G4 | Fast | p50 scan ≤ 60 s, p95 ≤ 180 s (MVP, no fix generation) |
| G5 | Cheap to run | Mean LLM cost per scan ≤ US$0.10; hard cap US$0.40 per scan |
| G6 | Honest verification (v1) | 0 findings ever labeled "verified" without machine-checkable evidence |
| G7 | Portfolio-grade engineering | Public repo with tests, CI, docs, live demo, and measured metrics |

### 3.2.1 Personal goals (project owner)
- It is a **side quest**: must be finishable in small chunks; MVP achievable in roughly 2 weekends of focused work.
- Should be **resume-worthy**: emphasis on measurable engineering decisions (token budgeting, scoring rubric validation, sandboxing) over "wrapper around an API."

### 3.3 Non-goals (explicitly out of scope)
- NG1: Replacing enterprise SAST/DAST/SCA suites or claiming compliance coverage (SOC2, PCI, etc.).
- NG2: Private repository scanning in MVP (planned v2 via GitHub App/OAuth).
- NG3: Auto-committing fixes, opening PRs, or writing to user repos (v2 maybe; MVP/v1 never writes to GitHub).
- NG4: Running the target repo's application, build, or arbitrary scripts in MVP. (v1.5 runs *existing tests* only, inside a sandbox, opt-in per repo size/language.)
- NG5: Full-language coverage. MVP covers Python, JavaScript, TypeScript.
- NG6: User accounts, teams, billing, SSO in MVP.
- NG7: Being funny at the expense of accuracy. Tone never overrides correctness.
- NG8: Roasting people. Roasts target code, never authors.

---

## 4. Target users

### 4.1 Personas

**P1 — "Vibe Coder Vik" (primary)**
- Builds apps with AI assistants; skims generated code; ships fast.
- Pain: does not know if the app leaks keys, has SQL injection, or will fall over.
- Wants: quick answer, plain language, copy-paste fixes, something funny to share.
- Success: sees "you committed an API key, rotate it now" before a stranger does.

**P2 — "Student Sam"**
- Building portfolio projects; wants recruiters to see clean repos.
- Pain: no feedback loop on code quality outside of grades.
- Wants: a checklist of what makes the repo look unprofessional (no README, no tests, no CI) and how to fix it.
- Success: takes score from Cooked to Lightly Toasted and puts the badge in the README.

**P3 — "Indie Ines"**
- Ships small SaaS/side projects solo; no security team.
- Pain: unsure about dependency vulnerabilities and auth mistakes.
- Wants: prioritized list (critical first), dependency CVEs, low noise.
- Success: fixes 3 real high-severity issues in an evening.

**P4 — "Curious Chris" (secondary, growth)**
- Scans famous repos and friends' repos for fun; shares screenshots.
- Success: gets a shareable card in under a minute.

### 4.2 Jobs to be done
- When I'm about to publish a repo, help me find embarrassing or dangerous problems so I can fix them before others see them.
- When I get a finding, help me understand why it matters and what to change, in language I understand.
- When my code is in decent shape, give me a badge I can show off.

---

## 5. Competitive landscape and positioning

| Product | Strength | Weakness for our audience | Our angle |
|---|---|---|---|
| Snyk | Deep SCA, trusted | Account + setup, enterprise feel | Zero setup, fun |
| SonarQube / SonarCloud | Mature quality gates | Heavy config, dashboards | One URL, one score |
| Semgrep | Great rules | CLI/CI knowledge required | We run it for you and explain results |
| GitHub CodeQL / Copilot Autofix | Native, integrated | Only inside GitHub Actions/Advanced Security | Works on any public URL instantly |
| CodeRabbit / Qodo | AI PR review | PR-time, team-oriented | Whole-repo snapshot + score |
| DeepSource / Codacy | Dashboards, history | Signup, config | No account |

**Positioning statement:** For developers who ship fast and review slowly, SkillIssue is the instant repo health check that tells you how cooked your code is, why, and how to fix it, unlike enterprise scanners that need setup or LLM chat prompts that hallucinate, because every finding is grounded in real tool output and every fix is honestly labeled.

**Defensible differentiators (in priority order):**
1. Grounded findings (tool signal + LLM triage; hallucination filters).
2. Honest fix verification labels (v1).
3. The Cooked Score: transparent, reproducible, shareable.
4. Tone and design that make people want to share it.

---

## 6. Product principles
1. **Truth over jokes.** Humor is a layer, never a substitute. If unsure, say so (confidence shown).
2. **Grounded before generative.** Deterministic scanners first; LLM second.
3. **Never claim what you did not check.** "Verified" requires evidence. Otherwise "Unverified."
4. **Zero-friction first run.** No login, no config, no installs.
5. **Small blast radius.** Never execute untrusted code outside a sandbox. Never write to user repos.
6. **Explain, don't just flag.** Every finding says what, why it matters, and what to do.
7. **Deterministic score.** Same commit + same pipeline version = same score.
8. **Cost-aware by design.** Budgets and caps are product features, not afterthoughts.

---

## 7. Scope by release

| Release | Theme | Included | Excluded |
|---|---|---|---|
| **MVP (v0.1)** | Roast | Public repo URL input; clone; static scanners; file sampling; LLM triage/explain; scoring; report page; shareable link; basic rate limit; feedback ("false positive") | Fix generation, verification, badges, history, login |
| **v1.0** | Fix | Fix suggestions as unified diffs; Tier-1 verification (rescan); share card image (OG); README badge; scan history per repo; roast-level toggle | Test execution, private repos, PR comments |
| **v1.5** | Trust | Tier-2 verification (lint/typecheck/existing tests before/after in sandbox); calibration improvements; more languages (Go) | LLM-written tests |
| **v2.0** | Team-ish | GitHub OAuth/App for private repos; PR comment bot/Action; trend charts; compare two repos; leaderboard of most-cooked public repos (opt-in) | Enterprise features |
| **Later / maybe** | Stretch | Tier-3 (LLM-written regression tests), VS Code extension, more languages (Java, Rust, PHP), self-hostable Docker image | n/a |

**MVP cut line (hard):** if a requirement is not marked `MVP` below, it does not block the first public release.

---

## 8. User journeys

### 8.1 Journey A — First scan (happy path)
1. User lands on the home page. Sees headline, URL field, "Scan repo" button, and 3 example repos to try.
2. Pastes `https://github.com/owner/repo`. Presses Enter or clicks "Scan repo".
3. Client validates format instantly (inline error if invalid).
4. API returns `202` with `scan_id`; UI navigates to `/scan/{id}` and opens a live progress stream (SSE).
5. Progress shows stages: *Cloning → Running scanners → Picking files → Asking the model → Scoring* with a rising probe gauge.
6. On completion, the UI transitions to the report: big cooked score, tier, subscores, file heat map, ranked findings.
7. User opens a finding, reads what/why/fix, copies the suggested diff (v1) or marks "not a real issue".
8. User clicks "Share": copies link (and in v1: downloads share card / copies badge markdown).

### 8.2 Journey B — Cached result
1. User scans a repo that was already scanned at the same commit SHA with the same pipeline version.
2. API returns `200`-style response with `cached: true` and the existing `scan_id`; UI jumps straight to the report with a "Scanned {time ago} at commit {sha7}. Rescan" note.
3. "Rescan" is disabled until the cooldown (10 min) passes or commit SHA changes.

### 8.3 Journey C — Failure
1. Repo is private/nonexistent/too large/unsupported. User sees a specific, actionable error (see §15) and can try another URL immediately.

### 8.4 Journey D — Improvement loop (v1)
1. User fixes issues, pushes, rescans. History view shows score over time and which findings disappeared/appeared (matched by fingerprint).
2. User adds the badge to README.

### 8.5 Journey E — Visitor via shared link
1. Visitor opens `/r/{owner}/{repo}` or a share card link, sees the report read-only, with a CTA "Scan your own repo".

---

## 9. Functional requirements

Priority key: **MVP**, **v1**, **v1.5**, **v2**.

### 9.1 Input and validation
| ID | Requirement | Pri |
|---|---|---|
| FR-1.1 | The system MUST accept these input forms: `https://github.com/{owner}/{repo}`, with optional `www.`, trailing slash, `.git` suffix, and `/tree/{branch}` (branch honored, path ignored); and shorthand `owner/repo`. | MVP |
| FR-1.2 | The system MUST reject any host other than `github.com` with the error `unsupported_host`. | MVP |
| FR-1.3 | Owner/repo names MUST match `^[A-Za-z0-9_.-]{1,100}$` after normalization; repo may not be `.` or `..`. | MVP |
| FR-1.4 | The UI MUST validate format client-side before submit and show inline errors without a network call. | MVP |
| FR-1.5 | The server MUST resolve the repo via the GitHub REST API to confirm it exists, is public, and get `default_branch`, `size`, `fork`, `archived`, `stargazers_count`, `language`, and the HEAD commit SHA of the target branch. | MVP |
| FR-1.6 | Forks, archived repos, and empty repos MUST be scannable but flagged (`is_fork`, `is_archived`); empty repos return `empty_repo`. | MVP |
| FR-1.7 | The UI SHOULD offer 3 example repos (owner-curated, deliberately including one very clean and one very cooked) as one-click buttons. | MVP |
| FR-1.8 | Users MAY pick a roast level (gentle / medium / unhinged) before scanning; default medium. Roast level affects only phrasing (`roast` field and UI copy), never scoring. | v1 |

### 9.2 Scan lifecycle
| ID | Requirement | Pri |
|---|---|---|
| FR-2.1 | Creating a scan MUST return immediately (`202`) with `scan_id`; work happens asynchronously. | MVP |
| FR-2.2 | A scan MUST progress through statuses: `queued → cloning → scanning → sampling → analyzing → scoring → completed`; v1 adds `fixing → verifying` between `scoring` and `completed`. Terminal states: `completed`, `failed`, `canceled`. | MVP |
| FR-2.3 | The API MUST expose progress via polling (`GET /scans/{id}`) and via SSE (`GET /scans/{id}/events`). | MVP |
| FR-2.4 | Every status transition MUST be recorded with timestamp in `scan_events`. | MVP |
| FR-2.5 | A user MUST be able to cancel a queued or running scan. | v1 |
| FR-2.6 | Scans MUST be cached by `(repo, commit_sha, pipeline_version, options_hash)`. A cache hit MUST NOT consume LLM budget or scanner time. | MVP |
| FR-2.7 | A scan MUST enforce wall-clock timeout of 10 minutes total (stage budgets in Architecture). On timeout, status `failed` with `error_code = scan_timeout`, unless partial results are usable (see FR-2.8). | MVP |
| FR-2.8 | If the LLM stage fails or times out but scanner findings exist, the scan MUST complete with `coverage = "scanners_only"` and a visible banner: "The AI pass failed, so this report only includes scanner results." | MVP |
| FR-2.9 | Jobs MUST be idempotent and retryable; a worker crash MUST NOT leave a scan stuck (heartbeat + reaper). | MVP |

### 9.3 Analysis pipeline
| ID | Requirement | Pri |
|---|---|---|
| FR-3.1 | Source acquisition MUST be shallow and pinned to the resolved commit SHA: primary method is the GitHub tarball at that SHA; fallback is a hardened shallow git clone (`--depth 1`, single-branch, no tags, no submodules, no LFS, hooks disabled). Symlinks, hardlinks, and special files MUST NOT be materialized. The pipeline status name remains `cloning` (UI label: "Fetching code"). | MVP |
| FR-3.2 | File filtering MUST skip: `node_modules`, `vendor`, `dist`, `build`, `.next`, `.venv`, `venv`, `__pycache__`, `.git`, lockfiles (as source; still read for dependency scan), minified files (`*.min.js`), source maps, binaries, images, fonts, files > 1 MB, generated files (header markers such as "auto-generated", "do not edit"), and files > 5,000 lines. | MVP |
| FR-3.3 | The system MUST detect languages by extension and compute per-language LOC (non-blank, non-comment where feasible). | MVP |
| FR-3.4 | The system MUST run these deterministic tools where applicable: Semgrep (rules baked in), Bandit (Python), ESLint with a fixed SkillIssue config (JS/TS), gitleaks (secrets), OSV-Scanner (dependency vulnerabilities from lockfiles/manifests), Lizard and Radon (complexity). | MVP |
| FR-3.5 | Tool output MUST be normalized into a common `RawSignal` schema before merging. | MVP |
| FR-3.6 | The system MUST sample files for LLM analysis using the ranking rules in Architecture §8; total LLM input MUST NOT exceed 150,000 tokens per scan. | MVP |
| FR-3.7 | The LLM MUST be asked to (a) triage scanner signals (confirm / reject / adjust severity), (b) explain each confirmed finding, (c) find additional logic/security/perf bugs in sampled code, and (d) return structured JSON via tool-use schema. | MVP |
| FR-3.8 | Hallucination guards MUST drop any LLM finding whose `file_path` was not in the sampled set, whose line range is outside the file, or whose quoted snippet does not appear (whitespace-normalized) in the file. | MVP |
| FR-3.9 | Findings from multiple sources on the same location MUST be deduplicated by fingerprint; the merged finding keeps all evidence. | MVP |
| FR-3.10 | Findings with confidence < 0.50 MUST NOT be shown or counted in the score. | MVP |
| FR-3.11 | Hygiene checks MUST be computed deterministically (no LLM): tests present, CI config present, README present and non-trivial, license present, `.gitignore` present, lockfile present, linter config present, `.env` committed. | MVP |
| FR-3.12 | Repo content MUST be treated as untrusted data in prompts (delimiters + nonce + instruction hierarchy). Any output not conforming to schema MUST be rejected and retried once. | MVP |

### 9.4 Findings
| ID | Requirement | Pri |
|---|---|---|
| FR-4.1 | Each finding MUST have: id, category, severity, confidence, title, explanation, file_path, line_start, line_end, snippet, language, rule_source, rule_id (nullable for LLM-only), fingerprint, evidence, status. | MVP |
| FR-4.2 | Category MUST be one of `security`, `bugs`, `performance`, `maintainability`, `hygiene`. | MVP |
| FR-4.3 | Severity MUST be one of `critical`, `high`, `medium`, `low` using the definitions in §12. | MVP |
| FR-4.4 | Findings MUST be ranked by `impact_rank` = severity weight × confidence, with ties broken by category priority (security > bugs > performance > maintainability > hygiene) then path. | MVP |
| FR-4.5 | The report MUST show at most 50 findings; the default view shows the top 10 with "Show more". Counts of hidden findings MUST be displayed. | MVP |
| FR-4.6 | Secrets found by gitleaks MUST be **masked** in the snippet and evidence (first 4 and last 2 characters only; the rest replaced by `•`). Full secret values MUST NEVER be persisted or logged. | MVP |
| FR-4.7 | Users MUST be able to mark a finding "Not a real issue" (anonymous; stored with IP hash) and "Helpful / Not helpful". | MVP |
| FR-4.8 | A finding flagged as false positive by the user MUST be visually dimmed for that browser session and recorded for evaluation; it MUST NOT change the public report or score. | MVP |

### 9.5 Scoring
| ID | Requirement | Pri |
|---|---|---|
| FR-5.1 | The score MUST be computed by the deterministic algorithm in §11 with no LLM involvement. | MVP |
| FR-5.2 | Report MUST show: overall score (0–100), tier name, 5 subscores, LOC analyzed, languages, coverage flag, pipeline version. | MVP |
| FR-5.3 | A "How is this calculated?" panel MUST show the formula summary, weights, and this scan's inputs. | MVP |
| FR-5.4 | Same commit + same pipeline version + same options MUST produce the same score (LLM nondeterminism is contained by caching and by persisting findings; rescoring from stored findings MUST be reproducible). | MVP |

### 9.6 Report UI
| ID | Requirement | Pri |
|---|---|---|
| FR-6.1 | Report header: repo name, commit short SHA, scan time, cooked gauge, tier, one-sentence summary. | MVP |
| FR-6.2 | Subscore section: five rows with score, tier glyph, and count of findings. | MVP |
| FR-6.3 | Heat map: file-tree treemap colored by per-file heat (weighted findings density); click a tile to filter findings to that file. | MVP |
| FR-6.4 | Findings list: filter by category, severity, file; sort by impact (default), severity, file. Persistent URL query params for filters. | MVP |
| FR-6.5 | Finding detail (drawer/inline): title, severity chip, category, confidence, location, snippet with highlighted lines, what/why/how, evidence links (CWE/OWASP where known), feedback buttons. | MVP |
| FR-6.6 | Code links MUST deep-link to `github.com/{owner}/{repo}/blob/{sha}/{path}#L{a}-L{b}`. | MVP |
| FR-6.7 | Report page MUST be server-rendered for shared links (SEO/OG) and work without JS for the read-only content where feasible. | v1 |
| FR-6.8 | Dark and light themes (system default + manual toggle). | MVP |
| FR-6.9 | Fully responsive from 360 px width. | MVP |

### 9.7 Fix suggestions (v1)
| ID | Requirement | Pri |
|---|---|---|
| FR-7.1 | For each of the top N findings (N = 10 default) with severity ≥ medium, the system MUST offer "Suggest a fix" generating a unified diff limited to the affected file(s). | v1 |
| FR-7.2 | Fix generation MUST be on-demand per finding (not for all findings by default) to control cost. | v1 |
| FR-7.3 | A fix diff MUST be validated: applies cleanly (`git apply --check`), touches only files in the repo, touches ≤ 3 files and ≤ 60 changed lines, adds no new dependencies unless the finding is a dependency vulnerability. | v1 |
| FR-7.4 | Fix UI MUST show diff, plain-language explanation, and verification badge (see §9.8). | v1 |
| FR-7.5 | System MUST NOT auto-apply anything to GitHub. Users copy the diff or download a `.patch` file. | v1 |

### 9.8 Fix verification (v1 / v1.5)
| ID | Requirement | Pri |
|---|---|---|
| FR-8.1 | Verification labels MUST be exactly: `verified`, `unverified`, `failed`, `not_run`. | v1 |
| FR-8.2 | **Tier 1** (v1): apply patch in a throwaway copy; confirm file still parses; re-run the specific tool/rule that produced the finding on the touched files; label `verified` only if the original signal disappears AND no new signals of severity ≥ medium appear in touched files. | v1 |
| FR-8.3 | Findings with no tool-backed signal (LLM-only) MUST be labeled `unverified` with the reason "No scanner rule covers this; review manually." They MUST NOT be labeled `verified`. | v1 |
| FR-8.4 | If the patch does not apply, does not parse, or the original signal remains or new signals appear, label `failed` and show why. Failed fixes MUST remain visible with the reason (transparency). | v1 |
| FR-8.5 | **Tier 2** (v1.5): run repo's lint/typecheck/test command before and after in the sandbox with no network; `verified` requires no regressions vs. baseline. Tests that already fail at baseline are excluded and reported. | v1.5 |
| FR-8.6 | Verification evidence (commands, exit codes, tool version, truncated output ≤ 4 KB) MUST be stored and viewable. | v1 |

### 9.9 Sharing and badges
| ID | Requirement | Pri |
|---|---|---|
| FR-9.1 | Every completed scan MUST have a stable public URL `/scan/{id}` and a friendly URL `/r/{owner}/{repo}` pointing at the latest scan. | MVP |
| FR-9.2 | "Copy link" and "Share" actions MUST be available in the report header. | MVP |
| FR-9.3 | Share card (PNG 1200×630) MUST be generated per scan showing repo, score, tier, top 3 issue titles (no code), and the SkillIssue wordmark. | v1 |
| FR-9.4 | Open Graph and Twitter Card meta MUST use the share card. | v1 |
| FR-9.5 | Badge endpoint `/badge/{owner}/{repo}.svg` MUST return an SVG (flat, 20 px high) with tier color and score, cache 1 hour. The UI MUST provide copy-ready Markdown/HTML. | v1 |
| FR-9.6 | Repo owners MUST be able to request removal of their report (see §18). | MVP (email/form), v2 (self-serve) |

### 9.10 History (v1)
| ID | Requirement | Pri |
|---|---|---|
| FR-10.1 | `/r/{owner}/{repo}` MUST show scan history (score over time, commit, date). | v1 |
| FR-10.2 | Diff between two scans MUST list findings fixed / new / unchanged by fingerprint. | v1 |

### 9.11 Abuse prevention, limits, budget
| ID | Requirement | Pri |
|---|---|---|
| FR-11.1 | Anonymous rate limit: 3 new scans per hour and 10 per day per IP (hashed); cache hits do not count. | MVP |
| FR-11.2 | Per-repo cooldown: 10 minutes between fresh scans of the same repo unless commit SHA changed. | MVP |
| FR-11.3 | Global daily spend cap (default US$5, configurable). When exceeded, new non-cached scans return `budget_exhausted` with reset time (00:00 UTC). | MVP |
| FR-11.4 | Queue depth cap 50; beyond that, `queue_full` with retry-after. | MVP |
| FR-11.5 | Bot protection: Cloudflare Turnstile (or equivalent) on scan creation if abuse detected (feature-flagged). | MVP (flag), on by default in prod |
| FR-11.6 | Denylist for repos/owners (takedown requests, abuse). | MVP |

### 9.12 Feedback and support
| ID | Requirement | Pri |
|---|---|---|
| FR-12.1 | Global "Report a problem" link (opens a prefilled GitHub issue on the SkillIssue repo or a form). | MVP |
| FR-12.2 | Takedown/contact email listed on the About/Legal page. | MVP |

### 9.13 Accounts (v2)
| ID | Requirement | Pri |
|---|---|---|
| FR-13.1 | GitHub OAuth login; scopes minimal (`read:user`; repo scope only via GitHub App with read-only contents permission for chosen repos). | v2 |
| FR-13.2 | Private repo scans MUST purge code from disk immediately after scan; only findings (with short snippets) are retained, user-deletable. | v2 |

### 9.14 Operations
| ID | Requirement | Pri |
|---|---|---|
| FR-14.1 | `/healthz` (liveness) and `/readyz` (DB, Redis, Docker socket reachable). | MVP |
| FR-14.2 | Structured JSON logs with `scan_id` correlation on every line. | MVP |
| FR-14.3 | Admin CLI/route (protected by static token) to: view scan, rerun scan, delete report, add to denylist, view budget ledger. | MVP |
| FR-14.4 | Metrics: scan duration by stage, success/failure by error code, LLM tokens and cost, cache hit rate, queue depth. | MVP |

---

## 10. User stories and acceptance criteria

**US-01 — Scan a repo by URL** (FR-1.*, FR-2.*)
- Given I am on the home page, when I paste a valid public GitHub URL and press Enter, then I am taken to a progress page within 1 second and see the first stage active.
- Given the URL has a trailing `.git` or `/tree/main`, then it is normalized and works.
- Given the URL is `https://gitlab.com/x/y`, then I see "SkillIssue only scans github.com repos" inline and no network request is made.

**US-02 — See the cooked score** (FR-5.*, FR-6.1–6.2)
- Given a scan completes, then I see an integer 0–100, a tier name, and five subscores, each with a label and a count of findings.
- Given I open "How is this calculated?", then I see weights and this scan's numbers and can reproduce the overall score by hand.

**US-03 — Understand a finding** (FR-4.*, FR-6.5)
- Given I open any finding, then I see title, severity, category, confidence, file:line with highlighted snippet, a "why this matters" paragraph, and how to fix it.
- Given the finding includes a secret, then the secret value is masked and there is a "Rotate this key" note.

**US-04 — Trust the results** (FR-3.8, FR-3.10)
- Given the LLM returns a finding pointing to a nonexistent line, then it is dropped and never shown; a `dropped_findings` counter increments in scan stats.

**US-05 — Filter and explore** (FR-6.3–6.4)
- Given I click a tile in the heat map, then the list filters to that file and the URL contains `?file=...`. Reloading preserves the filter.

**US-06 — Share** (FR-9.*)
- Given I click "Copy link", then the clipboard contains the permalink and a toast confirms "Link copied."
- Given I paste the link in a chat app, then a preview card shows score and tier (v1).

**US-07 — Rate limiting is understandable** (FR-11.*)
- Given I exceed 3 scans in an hour, then I see "You've used your 3 scans for this hour. Next slot opens at 14:32." and cached repos still load.

**US-08 — Failure is actionable** (§15)
- Given I scan a private repo, then I see "This repo is private or doesn't exist. SkillIssue can only scan public GitHub repos right now."

**US-09 — Get a fix** (v1; FR-7.*, FR-8.*)
- Given a finding with a scanner rule, when I click "Suggest a fix," then I see a diff and a verification pill: Verified / Unverified / Failed, each with plain-language reason.
- Given the finding is LLM-only, then the pill says "Unverified — no scanner covers this. Review manually." and never "Verified."

**US-10 — Badge** (v1; FR-9.5)
- Given I click "Add badge", then I get Markdown that renders a tier-colored badge with my score, and it updates after rescans (cache ≤ 1 hour).

**US-11 — Rescan after fixing** (v1; FR-10.*)
- Given I push a fix and rescan, then I see "3 findings fixed, 1 new" and my score trend.

**US-12 — Owner takedown** (FR-9.6)
- Given I own a repo, when I email the takedown address from an address matching a GitHub-verified email or place a `skillissue-optout` file in the repo root, then the report is removed within 3 business days and the repo denylisted.

---

## 11. Scoring specification (canonical)

### 11.1 Concepts
- **Cooked score:** integer 0–100. **Higher = more cooked (worse).**
- **Tiers:**
| Score | Tier | Meaning (UI one-liner) |
|---|---|---|
| 0–14 | **Raw** | "Barely touched by problems." |
| 15–34 | **Lightly Toasted** | "A few things to fix." |
| 35–59 | **Medium Well** | "Getting crispy. Prioritize the top issues." |
| 60–79 | **Cooked** | "Serious problems. Start with the critical ones." |
| 80–100 | **Burnt to a Crisp** | "Stop shipping. Fix the security issues first." |

### 11.2 Severity weights
| Severity | Weight `w_sev` |
|---|---|
| critical | 15 |
| high | 8 |
| medium | 3 |
| low | 1 |

### 11.3 Category raw points
For category `c`: `raw_c = Σ (w_sev(f) × confidence(f))` over shown findings `f` in `c` (confidence ≥ 0.50), excluding `hygiene` (hygiene is checklist-based, §11.5).

### 11.4 Normalization and category score
- `kloc = max(0.5, LOC_analyzed / 1000)`
- `density_c = raw_c / sqrt(kloc)`
- `score_c = 100 × (1 − exp(−density_c / k_c))`, rounded to nearest integer.

| Category | `k_c` |
|---|---|
| security | 20 |
| bugs | 25 |
| maintainability | 40 |
| performance | 40 |

(`k_c` values are initial defaults and MUST be calibrated in task **T-5.9** against the 30-repo reference set. Any change bumps `pipeline_version`.)

### 11.5 Hygiene score
Start at 0 and add penalties (cap 100):
| Check | Penalty |
|---|---|
| No tests detected (no test dirs/files/config) | 30 |
| No CI config (`.github/workflows`, `.gitlab-ci.yml`, etc.) | 15 |
| No README | 15 |
| README present but < 300 characters | 8 |
| No LICENSE | 5 |
| No `.gitignore` | 10 |
| No lockfile for a detected package manager | 10 |
| No linter/formatter config | 5 |
| `.env` (or similar secrets file) committed | 25 |

### 11.6 Overall
- `weighted = 0.35×security + 0.25×bugs + 0.15×maintainability + 0.10×performance + 0.15×hygiene`
- **Floors (applied after weighting):**
  - Any critical **security** finding with confidence ≥ 0.80 → overall ≥ 60.
  - Any **verified live-format secret** (gitleaks match on a provider-specific pattern) → overall ≥ 70.
- `overall = round(max(weighted, applicable_floor))`, clamped to [0, 100].

### 11.7 Worked example
Repo: 4,000 LOC analyzed (`kloc = 4.0`, `sqrt = 2.0`).
- Security: one high (conf 0.9) → raw 7.2 → density 3.6 → `100×(1−e^(−3.6/20))` = **16.5 → 17**
- Bugs: three medium (conf 0.8) → raw 7.2 → density 3.6 → k=25 → **13.4 → 13**
- Maintainability: five low (0.7) + two medium (0.7) → raw 7.7 → density 3.85 → k=40 → **9.2 → 9**
- Performance: three low (0.6) → raw 1.8 → density 0.9 → k=40 → **2.2 → 2**
- Hygiene: no tests (30) + no CI (15) + no LICENSE (5) → **50**
- Weighted = 0.35×17 + 0.25×13 + 0.15×9 + 0.10×2 + 0.15×50 = 5.95 + 3.25 + 1.35 + 0.20 + 7.50 = **18.25**
- No floor applies → overall **18 → Lightly Toasted**.

> Reality check to perform during calibration: real vibe-coded repos will have far more findings than this example. If most repos land under 20, the `k_c` values are too lenient and must be lowered. The target distribution on the reference set is roughly: 15% Raw, 25% Lightly Toasted, 30% Medium Well, 20% Cooked, 10% Burnt.

### 11.8 Reproducibility rules
- Score inputs (all shown findings with severity/confidence/category, LOC, hygiene results, pipeline version) are stored so the score can be recomputed offline.
- `pipeline_version` format: `{major}.{minor}.{patch}` where **major** = scoring formula change, **minor** = prompt/model/scanner-rule changes, **patch** = bug fixes with no score effect.

---

## 12. Findings taxonomy

### 12.1 Categories
| Category | Includes | Typical sources |
|---|---|---|
| **security** | Injection, hardcoded secrets, broken auth, unsafe deserialization, SSRF, path traversal, XSS, insecure crypto, vulnerable dependencies (CVEs), permissive CORS, debug mode in prod | Semgrep, Bandit, gitleaks, OSV, ESLint security rules, LLM |
| **bugs** | Null/undefined dereference, off-by-one, unhandled promise rejections, race conditions, resource leaks, wrong comparisons, dead branches, swallowed exceptions, incorrect async usage | ESLint, Semgrep, Bandit, LLM |
| **performance** | N+1 queries, blocking I/O in async paths, unbounded loops/allocations, missing pagination, re-renders, sync file I/O in request handlers, missing indexes hints | LLM, Semgrep, complexity signals |
| **maintainability** | Very high cyclomatic complexity, huge functions/files, deep nesting, duplicated logic, dead code, magic numbers, no types on public APIs, unclear naming (LLM only, low severity) | Lizard, Radon, ESLint, LLM |
| **hygiene** | Tests/CI/README/license/gitignore/lockfile/lint config/`.env` committed | Deterministic checks |

### 12.2 Severity definitions
| Severity | Definition | Examples |
|---|---|---|
| **critical** | Exploitable now with high impact; immediate action | Live API key/secret committed; SQL injection on a public route; RCE via `eval`/unsafe deserialization on user input |
| **high** | Likely exploitable or will cause user-visible failure/data loss | Missing auth check on sensitive route; known CVE (CVSS ≥ 7) in a used dependency; unhandled crash in main path |
| **medium** | Real weakness or defect with limited impact/conditions | Weak hashing for non-critical data; missing input validation; N+1 in a hot path; swallowed exception |
| **low** | Code smell or minor issue | Overly complex function; unused variable; missing docstring type hints |

### 12.3 Confidence semantics
| Range | Meaning | UI |
|---|---|---|
| ≥ 0.80 | Scanner-confirmed or LLM-confirmed with matching evidence | "High confidence" |
| 0.50–0.79 | Plausible; needs human judgment | "Medium confidence" |
| < 0.50 | Not shown, not scored | hidden (stored for evaluation) |

Confidence assignment rules (initial): scanner-only high-precision rules start at 0.85; scanner rules known noisy start at 0.60; LLM confirms scanner signal → +0.10 (cap 0.98); LLM rejects → −0.40; LLM-only finding starts at the model's self-reported confidence × 0.8 (cap 0.85) and requires the snippet-match guard.

---

## 13. Supported languages and coverage matrix

| Language | Static tools | LLM pass | MVP | Notes |
|---|---|---|---|---|
| Python | Semgrep, Bandit, Radon, Lizard, OSV (`requirements.txt`, `poetry.lock`, `Pipfile.lock`) | Yes | ✅ | |
| JavaScript / JSX | Semgrep, ESLint, Lizard, OSV (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) | Yes | ✅ | |
| TypeScript / TSX | Semgrep, ESLint (typescript-eslint parser, no type-aware rules in MVP), Lizard | Yes | ✅ | |
| Go | Semgrep, Lizard, OSV (`go.sum`) | Yes | v1.5 | |
| Java, Rust, PHP, Ruby, C/C++, C# | Semgrep (generic rules), Lizard | Yes (reduced) | ❌ | Shown as "Reduced coverage" if present in significant share |
| Others | Secrets + hygiene only | LLM best-effort | ❌ | |

If < 50% of analyzed LOC is in fully supported languages, the report MUST show a banner: "Reduced coverage: most of this repo isn't in a language SkillIssue fully supports yet."

---

## 14. Limits and quotas (canonical)

| Limit | Value | Behavior when exceeded |
|---|---|---|
| Repo size (GitHub API `size`) | 150 MB | `repo_too_large` |
| Tracked files considered | 10,000 | Sample by directory; flag `partial_coverage` |
| Analyzed LOC | 500,000 | Sample; flag `partial_coverage` |
| Single file size | 1 MB | Skipped |
| Single file lines | 5,000 | Skipped |
| Scan wall-clock | 10 min | `scan_timeout` (see FR-2.7/2.8) |
| LLM input tokens per scan | 150,000 | Stop sending chunks |
| LLM output tokens per scan | 30,000 | Stop asking |
| LLM cost per scan | US$0.40 hard cap; ≤ US$0.10 target mean | Stop LLM stage → `scanners_only` if nothing yet |
| Chunk size | ≤ 6,000 tokens | Split by function/class boundaries |
| Max chunks | 30 | Highest-ranked first |
| Findings shown | 50 | "N more hidden" |
| Snippet length | ≤ 15 lines | Truncate with `…` |
| Anon rate limit | 3/hour, 10/day per IP | `rate_limited` + reset time |
| Per-repo cooldown | 10 min | Serve cached |
| Queue depth | 50 | `queue_full` |
| Global daily budget | US$5 (configurable) | `budget_exhausted` |
| Report retention | 90 days (then deleted; badge continues to serve last score for 30 more days) | |
| Clone retention | Deleted immediately after scan; hard TTL 1 hour via janitor | |
| IP hash retention | 30 days | |

---

## 15. Edge cases and error handling

| Situation | Code | User-facing message (see `DESIGN.md` voice) | Notes |
|---|---|---|---|
| Invalid URL format | `invalid_url` | "That doesn't look like a GitHub repo URL. Try `owner/repo` or a full github.com link." | Client-side first |
| Non-GitHub host | `unsupported_host` | "SkillIssue only scans github.com repos for now." | |
| Repo not found/private | `repo_not_found` | "This repo is private or doesn't exist. SkillIssue can only scan public GitHub repos." | GitHub 404 |
| GitHub API rate limit | `github_rate_limited` | "GitHub is limiting us right now. Try again in {n} minutes." | Use auth token from server; ETag caching |
| Empty repo | `empty_repo` | "This repo has no code to scan yet." | |
| Repo too large | `repo_too_large` | "This repo is {size} MB. The limit is 150 MB." | |
| No supported code found | `no_supported_code` | "No Python, JavaScript, or TypeScript files found. Hygiene and secret checks ran; the score reflects those only." | Still completes with `coverage = "hygiene_only"` |
| Clone failure | `clone_failed` | "Couldn't download this repo. Try again in a minute." | 1 retry |
| Scanner crash (one tool) | (non-fatal) | Banner: "{tool} didn't finish; its results are missing." | Score flagged `partial` |
| All scanners fail | `scan_failed` | "Every scanner failed on this repo. This is on us; the failure was logged." | |
| LLM API error/timeout | (non-fatal) | See FR-2.8 | 2 retries with backoff |
| LLM returns invalid schema | (retry once, then drop chunk) | none | counter in stats |
| Prompt injection detected in repo content | (non-fatal) | none | Log `injection_suspected`; continue; never follow instructions |
| Monorepo | (non-fatal) | none | Sample per top-level package; per-directory heat map |
| Repo with only vendored/generated code | `no_supported_code` | as above | |
| Binary-heavy repo | (non-fatal) | none | binaries skipped |
| Duplicate URL submitted concurrently | (coalesce) | Both users attach to the same scan | Redis lock by cache key |
| Scan canceled | `canceled` | "Scan canceled." | v1 |
| Rate limited | `rate_limited` | See US-07 | |
| Budget exhausted | `budget_exhausted` | "SkillIssue hit today's budget. Cached reports still work. New scans reopen at 00:00 UTC." | |
| Queue full | `queue_full` | "Too many scans in line. Try again in a minute." | |
| Denylisted repo | `repo_opted_out` | "The owner of this repo asked not to be scanned." | |
| Server error | `internal_error` | "Something broke on our side. The failure was logged. Try again." | Include request id |

---

## 16. Non-functional requirements

### 16.1 Performance
- NFR-P1: Home page LCP < 1.5 s on a mid-range phone over 4G (static/edge-cached).
- NFR-P2: `POST /scans` p95 < 400 ms (excluding GitHub API latency > 1 s worst case).
- NFR-P3: Report page TTFB p95 < 500 ms (server-rendered from stored JSON).
- NFR-P4: Scan p50 ≤ 60 s, p95 ≤ 180 s for repos ≤ 50k LOC (MVP).
- NFR-P5: SSE events delivered within 500 ms of state change.

### 16.2 Reliability
- NFR-R1: Scan success rate ≥ 92% (excluding user errors such as private repos).
- NFR-R2: No stuck scans > 15 minutes (reaper marks `failed`).
- NFR-R3: Worker restarts do not lose queued jobs (Redis persistence or DB-backed queue).
- NFR-R4: Graceful degradation: LLM outage → scanners-only reports.

### 16.3 Security
- NFR-S1: Target repos are untrusted; all analysis runs in locked-down containers (no network, read-only FS, dropped capabilities, resource limits, non-root, seccomp default).
- NFR-S2: No target repo code executed in MVP. Tier-2 verification (v1.5) executes tests only in a sandbox with `--network none`.
- NFR-S3: Secrets found in repos are masked before storage; API keys for GitHub/Anthropic only in env/secret manager; never logged.
- NFR-S4: LLM output is treated as untrusted: schema-validated, HTML-escaped, markdown sanitized, URLs stripped or rel=nofollow noopener.
- NFR-S5: CSRF-safe design (no cookie auth in MVP); CORS restricted to the web origin; strict CSP.
- NFR-S6: Dependency scanning on SkillIssue itself (dogfooding) in CI.

### 16.4 Privacy
- NFR-PR1: No accounts, no cookies in MVP beyond a theme preference (localStorage).
- NFR-PR2: IP addresses only stored as salted hashes (rotate salt monthly); raw IPs are not persisted.
- NFR-PR3: Cookieless analytics (Plausible or self-hosted equivalent); no cross-site tracking; no third-party ad scripts.
- NFR-PR4: Public reports contain only short snippets (≤ 15 lines) of public code, with secrets masked.

### 16.5 Accessibility
- NFR-A1: WCAG 2.2 AA for all core flows.
- NFR-A2: Keyboard-only usable; visible focus; logical tab order; skip link.
- NFR-A3: Color is never the sole carrier of meaning (tier name + glyph + number always shown).
- NFR-A4: `prefers-reduced-motion` respected; `prefers-color-scheme` respected.
- NFR-A5: Screen reader semantics for gauge (`role="meter"` with `aria-valuenow`, `aria-valuetext` "42 out of 100, Medium Well").

### 16.6 Compatibility
- Latest 2 versions of Chrome, Edge, Firefox, Safari (macOS/iOS), Chrome Android. No IE.

### 16.7 Internationalization
- MVP: English only, but all UI strings in a message catalog (no inline literals) to allow later translation. Numbers/dates formatted via `Intl`.

### 16.8 Cost
- NFR-C1: Infrastructure ≤ US$25/month at low traffic (free tiers where possible) excluding LLM spend.
- NFR-C2: LLM spend governed by per-scan and daily caps (FR-11.3).

### 16.9 Maintainability
- NFR-M1: Test coverage ≥ 80% on scoring, normalization, hallucination guards, URL parsing, and sandbox wrapper; ≥ 60% elsewhere.
- NFR-M2: One-command local dev (`make dev`) and one-command test (`make test`).

---

## 17. Content and tone policy

### 17.1 Voice
- Plain, direct, a bit dry. Sentence case. Active voice. No filler. Errors do not apologize and always say what happened and what to do. Full voice guide in `DESIGN.md` §11.

### 17.2 Roast levels (v1; MVP ships "medium" only)
| Level | Intent | Example for "hardcoded API key" |
|---|---|---|
| Gentle | Neutral, encouraging | "There's an API key in this file. Move it to an environment variable and rotate it." |
| Medium (default) | Dry humor | "This API key is committed in plain text. Bold move. Rotate it before someone else uses it." |
| Unhinged | Chaotic humor, still accurate | "You pushed a live key to a public repo. Bots found it before you finished typing the commit message. Rotate it." |

### 17.3 Hard rules
1. Roast the **code**, never the **person**. No references to the author's skill, intelligence, appearance, identity, or background.
2. No slurs, no profanity in Gentle/Medium; mild profanity is **not** used even in Unhinged in MVP.
3. Security findings on real secrets are never joked about in a way that dilutes urgency: the action ("rotate") comes first.
4. The score is never described as a judgment of the developer.
5. Shared cards contain no code and no secrets.
6. LLM outputs are constrained: `roast` field ≤ 140 chars and passes a blocklist filter; on violation, fall back to the template roast for that finding type.

---

## 18. Legal and compliance

| Topic | Position / requirement |
|---|---|
| Scanning public repos | Public GitHub content is accessed via git clone / GitHub API under GitHub Terms; obey API rate limits; identify with a descriptive `User-Agent`. |
| Copyright / licenses | Stores only short snippets (≤ 15 lines) attributed by file path and commit SHA; does not redistribute repositories. Respect takedown requests. |
| Third-party rule licenses | Verify licenses of bundled scanners and rule sets before public launch (notably Semgrep registry rules' license terms, and OSV data). Record decisions in `MEMORY.md`. Prefer permissively licensed rules if terms are restrictive for a public service. |
| Opt-out | Owners can opt out via `skillissue-optout` file in repo root or email; denylist honored within 3 business days. |
| Privacy policy | Required before public launch: what is stored, retention, hashed IPs, analytics, deletion contact. |
| Security disclosure | `SECURITY.md` + `security.txt` in SkillIssue's own repo/site. |
| Defamation risk | Copy avoids claiming a repo/author is "insecure" as fact without evidence; reports state "findings", show confidence, and include a disclaimer: "Automated analysis; may contain errors." |
| Responsible handling of leaked secrets | Never store full secret; show masked; advise rotation; never validate a secret by calling the provider's API. |
| Children's data | Not targeted; no personal data collection beyond hashed IPs. |
| Export/compliance | No special export-controlled features. |

---

## 19. Analytics and success metrics

### 19.1 Events (cookieless)
| Event | Properties |
|---|---|
| `page_home_view` | referrer_bucket |
| `scan_submit` | source (input/example/shorthand), cached (bool) |
| `scan_error` | error_code |
| `scan_complete` | duration_ms, loc_bucket, coverage, score_tier |
| `report_view` | is_owner_flow (own scan vs. shared), tier |
| `finding_open` | category, severity |
| `finding_feedback` | kind |
| `share_click` | kind (copy_link, card, badge) |
| `fix_request` (v1) | severity |
| `fix_result` (v1) | verification_status |
| `rescan` (v1) | score_delta_bucket |

No user identifiers, no repo names in analytics events (repo names live only in the backend DB).

### 19.2 KPIs and targets (first 90 days after public launch)
| KPI | Target |
|---|---|
| Activation (submit → completed report) | ≥ 70% |
| Scan success rate | ≥ 92% |
| Median scan time | ≤ 60 s |
| Share rate | ≥ 15% of completed scans |
| Precision @ conf ≥ 0.8 (manual audit) | ≥ 70% |
| User-flagged false positives | ≤ 20% of high-confidence findings viewed |
| Mean cost per scan | ≤ US$0.10 |
| Repeat scan rate (v1) | ≥ 10% |

### 19.3 Evaluation program (quality)
- **Reference set:** 30 public repos (10 clean, 10 average, 10 messy, mix of Python/JS/TS) with hand-labeled issues for ≥ 10 findings each.
- Run the pipeline on the reference set for every minor/major `pipeline_version` change; track precision/recall/score distribution; store results in `eval/results/`.
- Regression gate in CI: score for golden repos must stay within ±3 points unless `pipeline_version` bumped.

---

## 20. Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | LLM false positives erode trust | High | High | Scanner grounding; snippet-match guard; confidence display; user feedback loop; precision audits |
| R2 | Cost blowout from abuse | Medium | High | Rate limits, budget caps, cache, chunk caps, Turnstile |
| R3 | Malicious repo attacks the worker (parser exploits, decompression bombs, symlink tricks) | Medium | High | Locked-down containers, no network, size/time limits, no symlink following, no execution in MVP |
| R4 | Prompt injection in repo content | High | Medium | Delimiting, nonce, schema-only output, validate paths/lines, ignore instructions, log |
| R5 | Scoring feels arbitrary | Medium | Medium | Transparent formula panel, calibration set, versioned pipeline |
| R6 | Repo owners object to public reports | Medium | Medium | Opt-out mechanism, disclaimer, short snippets only, denylist |
| R7 | Rule/tool license issues | Medium | Medium | License audit pre-launch; swap rule sets if needed |
| R8 | GitHub API rate limiting | Medium | Medium | Authenticated server token, ETags, caching, clone via git protocol for content |
| R9 | Scope creep kills the side quest | High | High | Hard MVP cut line; `TASK.md` phases; rules against scope expansion |
| R10 | "Wrapper" perception hurts resume value | Medium | Medium | Emphasize scanner pipeline, sampling, scoring calibration, sandbox, evals with numbers |
| R11 | Meme name limits credibility | Low (side project) | Low | Keep; product copy is precise; About page is serious |
| R12 | Fix verification claims are wrong | Medium | High | Strict labels, evidence storage, `unverified` default, Tier-1 only in v1 |
| R13 | LLM/model deprecation or price change | Medium | Medium | Model IDs in config; abstraction layer; eval before switching |
| R14 | Leaking secrets from scanned repos via our own storage/logs | Low | High | Masking at ingestion, redaction middleware in logs, tests that assert no full secret persists |

---

## 21. Dependencies and assumptions

**Dependencies:** GitHub API/network, Anthropic API, Docker runtime on worker host, Semgrep/Bandit/ESLint/gitleaks/OSV-Scanner/Lizard/Radon, Postgres, Redis, hosting for web (e.g., Vercel) and API/worker (e.g., Fly.io/Railway/VPS).

**Assumptions:**
1. Most target repos are small (< 50k LOC) hobby projects.
2. Scanning cost is dominated by the LLM stage; scanners are effectively free.
3. Owner will run a single worker instance initially (concurrency 2).
4. Traffic at launch is low (< 200 scans/day) with possible spikes from a viral share.

---

## 22. Release plan and milestones

| Milestone | Definition of done | Target effort (focused hours) |
|---|---|---|
| **M0 Foundations** | Repo, CI, lint, typecheck, DB migrations, docker-compose dev env | 8–12 |
| **M1 Pipeline core** | Clone + filter + scanners + normalization on CLI, against reference repos | 16–24 |
| **M2 LLM + scoring** | Sampling, triage prompt, schema, guards, scoring, golden tests | 16–24 |
| **M3 API + queue** | Endpoints, worker, SSE, caching, rate limits | 12–18 |
| **M4 Web MVP** | Home, progress, report, findings, heat map, dark mode | 20–30 |
| **M5 Hardening + launch (MVP)** | Sandbox tests, budget caps, legal pages, deploy, monitoring | 10–16 |
| **M6 v1 features** | Fix suggestions, Tier-1 verification, share card, badge, history | 24–36 |
| **M7 v1.5** | Tier-2 verification, Go support, calibration pass 2 | 20–30 |

Rough MVP total: **82–124 focused hours** (about 2–4 weekends if you are fast and disciplined; plan for more).

---

## 23. Open questions

| # | Question | Owner | Needed by |
|---|---|---|---|
| Q1 | Final tech stack confirmation (defaults in `ARCHITECTURE.md`)? | Owner | Before M0 |
| Q2 | Hosting choice and budget ceiling? | Owner | Before M5 |
| Q3 | Domain/name availability (`skillissue.*`) and trademark check? | Owner | Before public launch |
| Q4 | Semgrep rule licensing decision for a public service? | Owner | Before M5 |
| Q5 | Include an "About this project" page with the owner's name/links (resume value)? | Owner | Before launch |
| Q6 | Should shared reports be indexable by search engines, or `noindex` by default? (Default here: `noindex` until launch review.) | Owner | Before M5 |
| Q7 | Do we show the repo owner's avatar (from GitHub)? (Default: yes, public data.) | Owner | M4 |

---

## 24. Appendix

### 24.1 Glossary
| Term | Meaning |
|---|---|
| Cooked score | Overall 0–100 badness score (higher is worse) |
| Tier | Named band of the score (Raw … Burnt to a Crisp) |
| Finding | A single problem at a location with category, severity, confidence |
| Signal | A raw output item from a scanner before merging |
| Fingerprint | Stable hash used to dedupe findings and match across scans |
| Sampling | Choosing which files/chunks go to the LLM |
| Pipeline version | Version of scoring + prompts + rules; part of the cache key |
| Coverage | `full`, `partial`, `scanners_only`, or `hygiene_only` |
| Verification | Machine-checked confirmation that a fix removes a finding without introducing new ones |

### 24.2 Sample report (abridged JSON)
```json
{
  "scan_id": "b7d9f0e2-3a4c-4b6e-9a51-2d7c2f7c9d10",
  "repo": {"owner": "example", "name": "todo-app", "default_branch": "main"},
  "commit_sha": "3f2c9a7d1e5b4a8c0d6e9f1a2b3c4d5e6f708192",
  "pipeline_version": "0.1.0",
  "coverage": "full",
  "stats": {"loc_analyzed": 4012, "files_analyzed": 63, "languages": {"TypeScript": 3100, "Python": 912}, "dropped_findings": 3},
  "score": {"overall": 18, "tier": "Lightly Toasted",
            "subscores": {"security": 17, "bugs": 13, "maintainability": 9, "performance": 2, "hygiene": 50}},
  "findings": [
    {
      "id": "0a1b2c3d-...",
      "category": "security",
      "severity": "high",
      "confidence": 0.90,
      "title": "SQL query built from user input",
      "explanation": "The `id` from the request is concatenated into the SQL string, so a crafted value can change the query. Use a parameterized query.",
      "roast": "Bold of you to trust the internet with your database.",
      "file_path": "server/routes/users.ts",
      "line_start": 41, "line_end": 43,
      "snippet": "const rows = await db.query(`SELECT * FROM users WHERE id = ${req.params.id}`);",
      "language": "typescript",
      "rule_source": "semgrep",
      "rule_id": "javascript.express.security.audit.sql-injection",
      "evidence": {"cwe": ["CWE-89"], "owasp": ["A03:2021"]},
      "fingerprint": "sha256:9c1e...",
      "status": "open"
    }
  ]
}
```

### 24.3 Example repos for the home page (owner to choose before launch)
- One deliberately clean small repo (expected Raw/Lightly Toasted).
- One deliberately messy repo created by the owner for demos (expected Cooked/Burnt) containing safe, fake secrets (e.g., obviously fake keys) so demos never involve real credentials.
- One famous open-source project for curiosity (expected mixed).

### 24.4 Change log
| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-09-22 | Initial draft |
