# SkillIssue — Memory

Living log of decisions, status, and things future-you (or another contributor) needs to know that aren't captured elsewhere. This file is meant to be edited constantly. It is not a design doc — `PRD.md`, `ARCHITECTURE.md`, and `DESIGN.md` are the source of truth for *what* and *how*; this file is the source of truth for *what actually happened and why*.

Companion docs: `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `TASK.md`, `RULES.md`.

---

## How to use this file

- **Update it at the end of every work session**, even a short one. Future-you will not remember why a decision was made; write it down now.
- **Decisions** go in §2, newest first, with status `Proposed / Decided / Reversed`. Never delete a decision — mark it `Reversed` and explain why, and leave the old row so the history is visible.
- **Status** (§1) is the current snapshot, not a log — overwrite it each session.
- **Running log** (§4) is append-only, newest entry at the top, dated. Keep entries short (3–8 lines). Link to PRs/commits where useful.
- If a decision here contradicts `PRD.md`/`ARCHITECTURE.md`/`DESIGN.md`, **update those docs in the same session** and note it in the log. This file should never be the only place a real decision lives long-term — it's the scratch pad that later gets folded into the canonical docs.
- Numbers and specs live in `PRD.md`/`ARCHITECTURE.md`; don't duplicate them here beyond what's needed to explain a decision.

---

## 1. Current status snapshot

*(Overwrite this section each session. Last updated: 2026-09-22 — initial draft, no build work started yet.)*

- **Phase:** Pre-P0. Docs drafted (PRD, Architecture, Design, Task, Rules). No code written yet.
- **Next up:** Spikes S-1..S-4 (see `TASK.md`), then T-0.1 (confirm stack) and T-0.2 (repo skeleton).
- **Blocking questions open:** PRD §23 Q1–Q7 all still open. See §3 below for tracking.
- **Budget/cost spent so far:** $0 (no infra running).
- **Known risks active right now:** none yet — nothing built.

---

## 2. Decisions (ADR-style, newest first)

> Format: **D-XXX — Title** · Status · Date · Context · Decision · Alternatives considered · Consequences · Revisit when

Architecture-level decisions that are stable and load-bearing are duplicated as ADRs in `ARCHITECTURE.md` §22 — keep the two in sync. This section can also hold smaller, less permanent decisions that don't warrant a formal ADR (copy wording, which repo to use as a demo, etc).

### D-000 — Template (copy this for new entries)
- **Status:** Proposed
- **Date:** YYYY-MM-DD
- **Context:** Why did this need a decision?
- **Decision:** What was decided.
- **Alternatives considered:** What else, and why not.
- **Consequences:** What this makes easier/harder; what it locks in.
- **Revisit when:** Concrete trigger condition, not "later."

*(No real decisions logged yet — the spikes and T-0.1 will produce the first ones: model/hosting/stack confirmation, Semgrep rule licensing, tarball vs. clone as primary source.)*

### D-001 — Semgrep rules cannot be redistributed under the Semgrep Rules License v1.0
- **Status:** Decided
- **Date:** 2026-09-22
- **Context:** Spike S-1. The architecture (ADR-011) baked Semgrep registry rules into the scanner image so `--network none` works. Before writing that, we had to verify the license permits it.
- **Decision:** **Do not bundle Semgrep registry rules into the scanner image.** The Semgrep Rules License v1.0 explicitly forbids distributing the rules OR making them available to others as a service. Both apply to SkillIssue (public Docker image + public scanning service).
- **Alternatives considered:**
  - **Pay for Semgrep Pro/Enterprise** (Teams $30/mo/contributor, Enterprise custom) — may grant redistribution rights; not confirmed without contacting sales. Even if it does, it's a recurring cost for a side project.
  - **Switch to a different scanner with permissive-licensed rules** — Bandit (Apache 2.0) for Python, ESLint (MIT) for JS/TS, gitleaks (MIT) for secrets, OSV-Scanner (Apache 2.0) for deps. None cover the cross-language Semgrep rulesets.
  - **Run Semgrep without baked rules, allow network on the scanner** — kills the offline/sandbox design and reopens the trust boundary.
  - **Write our own rule packs** — months of work, expertise we don't have.
- **Consequences:**
  - **Scanner container must reach the network** for Semgrep to fetch rules at runtime, OR we replace Semgrep with a stack that doesn't need it.
  - This breaks the "scanner container has no network" assumption in ARCHITECTURE §11.2. Network must be allowed only to `semgrep.dev` / the rules registry endpoint, not arbitrary outbound.
  - Alternative: drop Semgrep entirely and lean on Bandit (Python), ESLint security plugins (JS/TS), plus the LLM pass for cross-language coverage. This is a major architectural change that simplifies the stack and removes one of the heavier dependencies.
- **Revisit when:** If Semgrep Inc offers a redistribution/SaaS license for OSS-side-projects at a sustainable price, OR we decide the cost is acceptable as a project expense.

### D-002 — Drop Semgrep from the scanner stack; use Bandit + ESLint security plugins + LLM instead
- **Status:** Proposed
- **Date:** 2026-09-22
- **Context:** Consequence of D-001. With Semgrep out, we need cross-language static analysis to anchor findings.
- **Decision (proposed):** Remove Semgrep. Stack becomes:
  - **Python:** Bandit (Apache 2.0) + Radon (MIT) + Lizard (GPL — **need to verify license compatibility for a service**) for complexity.
  - **JS/TS:** ESLint (MIT) with `eslint-plugin-security` (MIT) + correctness rules.
  - **Secrets:** gitleaks (MIT).
  - **Dependencies:** OSV-Scanner (Apache 2.0).
  - **Cross-language gaps:** LLM pass covers what static analyzers miss.
- **Consequences:** Need to verify Lizard license (GPLv3 may be a problem for a service). ADR-011 needs to be rewritten. The scanner image becomes simpler (no Python for Semgrep runtime). Confidence in cross-language findings drops slightly (LLM-only for anything not covered by the per-language tools), which means more reliance on the LLM pass — cost implication.
- **Revisit when:** When we know the Lizard license situation, OR if a permissive-licensed cross-language tool emerges.

---

## 3. Open questions tracker

Mirrors `PRD.md` §23. Update status here as they close; when one closes, also update the PRD row and add a decision entry above.

| # | Question | Status | Notes |
|---|---|---|---|
| Q1 | Final tech stack confirmation | Open | Defaults in `ARCHITECTURE.md` §3 assumed until spikes complete |
| Q2 | Hosting choice and budget ceiling | Open | Depends on S-2 (rootless Docker on target VPS) |
| Q3 | Domain/name availability, trademark check | Open | T-0.11 |
| Q4 | Semgrep rule licensing for a public service | Open | S-1, T-9.6 |
| Q5 | About page owner name/links | Open | Personal call, no blocker |
| Q6 | Shared reports indexable or `noindex`? | Open (default: `noindex` until launch review) | T-9.10 |
| Q7 | Show repo owner avatar? | Leaning yes | `DESIGN.md` DQ4 defaults to yes |

---

## 4. Running log

> Newest entry at the top. One entry per work session. Keep it honest — include dead ends and things that took longer than expected, not just wins.

### 2026-09-22 — Initial planning session
- Wrote `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `TASK.md`, `RULES.md`, and this file from scratch based on the project pitch (AI code health platform, "cooked score").
- Owner confirmed: this is a **side quest**, not a startup. That reframed scope decisions throughout — MVP is deliberately small (Phases 0–9 in `TASK.md`), fix generation and verification pushed to v1/v1.5.
- Key design tension resolved: LLM output must never be trusted blindly. Landed on "scanners first, LLM triages and explains" as the core architectural bet (ADR-001). This is the thing that makes the project defensible and resume-worthy, not the AI wrapper part.
- Scoring formula (PRD §11) was worked through by hand with a concrete example to sanity-check it before committing to the shape — result: overall 18 ("Lightly Toasted") for a plausible small repo. Flagged that real-world calibration (T-5.9) will very likely need to adjust the `k_c` constants; the current values are placeholders, not measured.
- Source acquisition: originally spec'd as plain `git clone`. On review, switched primary method to **GitHub tarball at pinned SHA** with hardened clone as fallback (ADR-002) — avoids parsing arbitrary git objects from an untrusted source, simpler to sandbox. Corrected an earlier idea to use file churn (recently-changed files) in sampling, since a shallow tarball has no git history — removed that signal from the sampling formula (see `ARCHITECTURE.md` §7.6 note).
- Verification design (v1/v1.5) was the trickiest part: had to be very explicit that "verified" is a strong claim and must never be applied to LLM-only findings with no scanner backing. Encoded this as a hard rule in `RULES.md`, not just a suggestion, because getting this wrong would undermine the whole trust story.
- Nothing built yet. Next session: run the four spikes (S-1..S-4) before writing any real application code — they're cheap and will change assumptions (rule licensing, sandbox flags, extraction safety, prompt quality/cost) baked into the architecture doc.

---

## 5. Things that surprised us / would do differently

*(Fill in as you go. Examples of the kind of thing that belongs here: "Semgrep's registry rules turned out to be licensed in a way that blocked X, had to switch to Y"; "tarball extraction was 3x faster than git clone, worth leading with"; "the LLM kept hallucinating line numbers until we added absolute line numbers to chunk rendering — huge quality jump.")*

- (none yet)

---

## 6. Parking lot

Ideas that came up but are explicitly **not** being done now, so they stop popping into your head mid-task. Not the same as the v2 backlog in `TASK.md` (that's roadmapped; this is "maybe, someday, unlikely").

- Leaderboard of most-cooked public repos, opt-in — fun but real moderation/legal surface area, revisit after v2 accounts exist.
- Slack/Discord bot that posts a repo's score on demand.
- "Roast battle" — compare two repos head to head, publicly rank friend groups. Fun but a harassment vector if not careful; would need real thought before building.
- Self-hosted / on-prem version for companies who won't send code to a hosted service. Interesting but a different product (enterprise), explicitly a non-goal for now.

---

## 7. Contacts and access (fill in privately; do not commit real secrets here)

| What | Where | Notes |
|---|---|---|
| Domain registrar | TBD (Q3) | |
| Hosting (VPS) | TBD (Q2) | |
| Anthropic API key | secrets manager, not here | worker-only, per `ARCHITECTURE.md` §15.2 |
| GitHub server token | secrets manager, not here | public read only, no scopes |
| Error tracking (Sentry) | TBD | |
| Uptime monitor | TBD | |
