# SkillIssue — Design Specification

| Field | Value |
|---|---|
| Document version | 0.1 (draft) |
| Date | 2026-09-22 |
| Scope | Visual identity, tokens, layout, components, motion, copy, accessibility, share assets |
| Companion docs | `PRD.md` (what), `ARCHITECTURE.md` (how), `RULES.md` (implementation rules), `TASK.md` |

> Contrast ratios in this document were **computed** (WCAG 2.x relative luminance), not estimated. If you change a hex value, recompute and update the table (`TASK.md` T-7.3 includes a script for this).

---

## 1. Design brief (grounded in the subject)

- **Subject:** a web tool where a developer pastes a GitHub repo URL and learns how "cooked" their code is.
- **Audience:** students, indie hackers, vibe coders; people who read memes and read code.
- **Primary job of the design:** turn a scary technical scan into something legible in five seconds (score, tier, top problems) and fun enough to screenshot, **without ever making the data look less trustworthy.**
- **Tone:** dry, precise, a little cheeky. The interface is calm; the *results* are hot.

## 2. Design plan (two-pass, reviewed against the brief)

### 2.1 First pass (what I would produce by default)
Dark near-black UI, one neon orange/red "fire" accent, flame icons, gradient glows, rounded cards with soft shadows, monospace labels everywhere, ALL-CAPS eyebrows.

### 2.2 Review against the brief: what changed and why
| Default instinct | Problem | Revised choice |
|---|---|---|
| "Cooked" → fire, orange on black | It is the generic "AI product" look (near-black + a single vivid accent); it also makes *everything* look hot, so the score loses meaning | **Invert it:** the interface is cold (pale steel-blue, ink text). Heat colors appear **only** where code is actually cooked. Color becomes information, not decoration |
| Flame icons | Cliché; says nothing specific | The signature object is a **probe thermometer** (a kitchen meat probe / lab thermometer): it *measures* doneness, matching the "cooked" joke and the "measuring a repo" job |
| Identical rounded cards | Chops content into a SaaS template | Sections separated by whitespace and a single hairline where grouping needs it; only the detail panel and popovers are "panels" |
| Mono font for all small labels | Template chrome | Mono **only for code and file paths**. UI labels use the sans |
| ALL-CAPS tracked eyebrows, "01 / 02 / 03" | Decoration | None. Numbering appears only where order matters (scan stages) |
| Gradient washes | Decoration | The only gradient-like element is the heat scale, which is a legend of real data |
| Scattered fade-and-slide entrances | Reads as generated | **One** orchestrated moment: the probe filling to the final score. Everything else responds only to user action |

### 2.3 Token summary
- **Color:** Frost `#E6EDF3`, Sheet `#F5F8FA`, Cold Ink `#17263A`, Probe `#0B7A75`; heat scale Raw `#2B6CC4` · Toasted `#F0C24B` · Medium Well `#F08A24` · Cooked `#CF3626` · Burnt `#4A2A22`.
- **Type:** Bricolage Grotesque (UI + display), Source Serif 4 (explanatory reading text), JetBrains Mono (code and paths only).
- **Layout:** left-aligned, 1120 px container, 12 columns; report is master/detail (findings list + sticky detail).
- **Principles:** (1) cold interface, hot data; (2) the probe is the one memorable object; (3) numbers and names always travel together; color never alone; (4) roast in the words, never in the layout; (5) quiet everything else.

---

## 3. Brand

### 3.1 Name and wordmark
- Written **SkillIssue** (one word, capital S and I) in text. Wordmark set in Bricolage Grotesque 800, width axis 75, letter-spacing −0.01em.
- Minimum size 96 px wide. Clear space = height of the "S" on all sides.
- Never: all caps, italics, drop shadows, gradients, or the probe replacing a letter.

### 3.2 Mark (the probe)
A vertical thermometer capsule with a bulb, three tick marks on the right, and a fill. Used as favicon, app icon, and the hero object at large size.

```svg
<!-- mark.svg : 24×40 viewBox. fill color = tier color (default Cooked #CF3626) -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 40" role="img" aria-label="SkillIssue probe">
  <rect x="7" y="2" width="10" height="26" rx="5" fill="none" stroke="#17263A" stroke-width="2"/>
  <circle cx="12" cy="32" r="6" fill="#CF3626" stroke="#17263A" stroke-width="2"/>
  <rect x="10" y="12" width="4" height="20" rx="2" fill="#CF3626"/>
  <path d="M19 8h3M19 15h3M19 22h3" stroke="#17263A" stroke-width="2" stroke-linecap="round"/>
</svg>
```
Favicon: mark only on Frost square with 4 px padding (16, 32, 180 px). Dark-mode favicon uses `#3CC6BE`-outlined variant via `prefers-color-scheme` media in the SVG favicon.

### 3.3 Voice in one line
Direct, dry, specific. Full guide in §12.

---

## 4. Color

### 4.1 Core palette (light)
| Token | Hex | Role |
|---|---|---|
| `--frost` | `#E6EDF3` | Page background |
| `--sheet` | `#F5F8FA` | Raised surfaces (detail panel, inputs, popovers) |
| `--ink` | `#17263A` | Primary text, icons, outlines |
| `--ink-muted` | `#4A5B6E` | Secondary text |
| `--steam` | `#C5D2DD` | Decorative dividers (not for controls) |
| `--field-border` | `#7D8FA3` | Input/control borders (meets 3:1) |
| `--probe` | `#0B7A75` | Links, primary buttons, focus ring, "measuring" state |
| `--probe-ink` | `#FFFFFF` | Text on `--probe` |

### 4.2 Heat scale (data only)
| Tier / severity use | Token | Fill | Text on fill | Text-safe variant (text on Sheet) |
|---|---|---|---|---|
| Raw · severity low | `--heat-raw` | `#2B6CC4` | white | `#1F5FB8` |
| Lightly Toasted · severity medium | `--heat-toasted` | `#F0C24B` | ink | `#7A5B00` |
| Medium Well · severity high | `--heat-medwell` | `#F08A24` | ink | `#A85A0C` |
| Cooked · severity critical | `--heat-cooked` | `#CF3626` | white | `#B3301F` |
| Burnt to a Crisp (tier only) | `--heat-burnt` | `#4A2A22` | white | `#4A2A22` |

### 4.3 Computed contrast (light)
| Pair | Ratio | Use OK for |
|---|---|---|
| Ink on Frost | 12.93 | All text |
| Ink on Sheet | 14.32 | All text |
| Ink-muted on Frost | 5.90 | Secondary text |
| Ink-muted on Sheet | 6.54 | Secondary text |
| Probe on Sheet | 4.86 | Body-size links/text |
| Probe on Frost | **4.38** | **Fails 4.5 for body text: never set Probe-colored body text on Frost** (use Ink + underline, or place on Sheet) |
| White on Probe | 5.18 | Button text |
| Field border `#7D8FA3` on Sheet | 3.11 | Control boundaries (≥ 3:1) |
| White on Raw | 5.19 | Chip text |
| Ink on Toasted | 9.11 | Chip text |
| Ink on Medium Well | 6.09 | Chip text |
| White on Cooked | 4.99 | Chip text |
| White on Burnt | 12.76 | Chip text |
| Text-safe Raw `#1F5FB8` on Sheet | 5.81 | Text |
| Text-safe Toasted `#7A5B00` on Sheet | 5.92 | Text |
| Text-safe Medium Well `#A85A0C` on Sheet | 4.76 | Text |
| Text-safe Cooked `#B3301F` on Sheet | 5.86 | Text |

**Graphic (non-text) contrast against Sheet:** Raw 4.87 · Cooked 4.68 · Burnt 11.97 pass 3:1. **Toasted (1.57) and Medium Well (2.35) fail 3:1**, therefore *every* Toasted/Medium Well fill that carries meaning (gauge fill, bars, treemap tiles, chips) MUST have a 1.5 px Ink outline **and** a text/number label. Never rely on hue alone.

### 4.4 Dark theme ("Cold Cellar")
| Token | Hex | Notes |
|---|---|---|
| `--frost` (bg) | `#0F1B2B` | |
| `--sheet` | `#172740` | |
| `--ink` | `#E3ECF5` | 14.51 on bg · 12.55 on sheet |
| `--ink-muted` | `#9DB0C4` | 7.79 on bg · 6.74 on sheet |
| `--steam` | `#2B4160` | Decorative only |
| `--field-border` | `#7590B2` | 4.56 on sheet · 5.27 on bg |
| `--probe` | `#3CC6BE` | 8.26 on bg · 7.15 on sheet; button text is `#0F1B2B` (8.26) |
| Heat text-safe (dark) | Raw `#6FA8EE` (6.08 on sheet) · Toasted `#F0C24B` (8.94) · Medium Well `#F5A04A` (7.15) · Cooked `#FF7A66` (5.87) · Burnt `#C98A78` (5.28) | Fills stay the same as light; outlines switch to `--ink` (light) so Toasted/Medium Well tiles remain delineated |

### 4.5 Usage rules
1. Heat colors appear **only** for: tier, severity, heat map, gauge fill, badges, share cards. Never for buttons, links, backgrounds of sections, or decoration.
2. Every use of a heat color is paired with a **name** (tier/severity word) and, where space allows, a **glyph** and a **number**.
3. Probe teal = interactive/brand-action and the neutral "measuring" state. It is never used to indicate quality.
4. Error banners use Cooked text-safe + icon + words (no full-red backgrounds).
5. No pure black or pure white surfaces; text on dark surfaces is `--ink` (dark theme) not `#FFF` except on filled chips.

---

## 5. Typography

### 5.1 Families
| Role | Family | Axes/weights | Why |
|---|---|---|---|
| **Display + UI** | **Bricolage Grotesque** (variable) | wght 400–800, wdth 75–100, opsz auto | Characterful grotesque; condensed widths give the hero and score numerals presence; humanist quirks keep it from reading as a default sans |
| **Reading text** (explanations, how-it-works, legal) | **Source Serif 4** (variable) | wght 400, 600; opsz auto | Distinct from the sans; comfortable for multi-sentence explanations; slightly more line-height per guidance |
| **Code and paths only** | **JetBrains Mono** | 400, 600 | Functional necessity for snippets, diffs, file paths, line numbers |

Loading: `next/font/google` (self-hosted at build, no runtime requests to Google), `display: swap`, subset `latin` (+ `latin-ext` if needed), preload Bricolage only. Fallback stacks:
- Sans: `"Bricolage Grotesque", ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif`
- Serif: `"Source Serif 4", ui-serif, Georgia, "Times New Roman", serif`
- Mono: `"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace`

### 5.2 Scale (base 16 px, ratio 1.25, fluid at the top end)
| Token | Size | Line-height | Family / weight / width | Tracking | Use |
|---|---|---|---|---|---|
| `--t-caption` | 12.8 px | 1.4 | Sans 500 | +0.01em | Timestamps, footnotes |
| `--t-small` | 14 px | 1.45 | Sans 450 | 0 | Metadata, chips, table cells |
| `--t-ui` | 16 px | 1.5 | Sans 450 | 0 | Buttons, inputs, nav |
| `--t-read` | 18 px | 1.65 | Serif 400 | 0 | Explanations, prose |
| `--t-h4` | 20 px | 1.3 | Sans 600 | 0 | Finding titles |
| `--t-h3` | 25 px | 1.25 | Sans 650 | −0.005em | Section titles |
| `--t-h2` | 31 px | 1.2 | Sans 700, wdth 90 | −0.01em | Page section headings |
| `--t-h1` | clamp(39px, 5vw, 49px) | 1.1 | Sans 750, wdth 80 | −0.01em | Page titles |
| `--t-display` | clamp(52px, 9vw, 96px) | 1.0 | Sans 800, wdth 75 | −0.02em | Home headline |
| `--t-score` | clamp(96px, 16vw, 168px) | 0.9 | Sans 800, wdth 75, lining nums | −0.02em | The score numeral |
| `--t-code` | 14 px | 1.55 | Mono 400 | 0 | Snippets, paths |

### 5.3 Rules
- **Measure:** sans UI text ≤ 72ch; serif reading text ≤ 66ch; headlines ≤ 16ch where possible.
- Sentence case everywhere. **No ALL CAPS labels.** No tracked-out eyebrows.
- **No single-word accenting** in headlines (no lone italic/colored/bold word).
- Numerals: use lining figures; in tables and subscore columns use `font-variant-numeric: tabular-nums` (Bricolage supports OpenType `tnum` via features where available; if a fallback font is active, alignment is not guaranteed; acceptable).
- Headline text is a design element on the home page (large, condensed, tight) but body text stays quiet.
- Code snippets: line numbers in `--ink-muted`, highlighted lines with a 3 px left bar in the severity heat color **plus** a subtle Sheet-darker background (`color-mix(in srgb, var(--ink) 6%, var(--sheet))`).

---

## 6. Space, layout, shape

### 6.1 Spacing scale (4 px base)
`--s-1 4` · `--s-2 8` · `--s-3 12` · `--s-4 16` · `--s-5 24` · `--s-6 32` · `--s-7 48` · `--s-8 64` · `--s-9 96` · `--s-10 128`
Vertical rhythm: sections separated by `--s-8` (desktop) / `--s-7` (mobile); related items `--s-3`–`--s-4`.

### 6.2 Grid and breakpoints
| Name | Min width | Columns | Gutter | Side margin |
|---|---|---|---|---|
| `xs` | 360 | 4 | 16 | 16 |
| `sm` | 640 | 8 | 24 | 24 |
| `md` | 960 | 12 | 24 | 32 |
| `lg` | 1280 | 12 | 24 | auto (container max **1120**) |
Content is **left-aligned** by default. Center alignment is only used inside the share card gauge and empty/error states' icon. Justified text is never used. Numbers in tables are right-aligned.

### 6.3 Shape
| Token | Value | Applies to |
|---|---|---|
| `--r-none` | 0 | Sections, dividers, code blocks (flush) |
| `--r-2` | 2 px | Treemap tiles, inline `code` |
| `--r-control` | 6 px | Inputs, buttons, select |
| `--r-panel` | 10 px | Detail panel, popovers, banners |
| `--r-sheet` | 16 px (top corners) | Mobile bottom sheet |
| `--r-pill` | 999 px | Chips, verification pills |
Different roles use different radii on purpose; no universal radius.

### 6.4 Borders, elevation, z-index
- Structural rule: 1 px `--steam` between page sections **only where it separates independent groups** (header/report body; list/detail). Not around every block.
- Control border: 1 px `--field-border`.
- Elevation: **none** for content. Popovers/drawer/bottom sheet only: `0 8px 24px rgba(23, 38, 58, 0.18)` (light) / `0 8px 24px rgba(0, 0, 0, 0.5)` (dark).
- z-index: base 0 · sticky header 10 · sticky detail 5 · popover 30 · drawer/sheet 40 · toast 50 · skip link 60.

### 6.5 Focus
2 px solid `--probe` outline, 2 px offset, on all interactive elements (`:focus-visible`). On `--probe` filled buttons, focus ring is `--ink` 2 px + 2 px `--sheet` gap. Never remove outlines.

---

## 7. Screens and wireframes

> ASCII is layout intent, not pixel spec. `▮` = probe fill, `░` = quiet area.

### 7.1 Home (`/`)
Layout concept: left column = message and input; right column = the **idle probe** (empty tube, ticks and tier names visible). The probe becomes the same object in scan and report views (continuity).

```
md ≥ 960
┌──────────────────────────────────────────────────────────────────────────────┐
│ SkillIssue                                   How scoring works  About   ☾    │
│                                                                              │
│ How cooked                                             ┌─┐  Burnt to a crisp│
│ is your code?                                          │ │  ── 80           │
│ (display 96px, condensed)                              │ │  Cooked          │
│                                                        │ │  ── 60           │
│ Paste a public GitHub repo. Get a score, the           │ │  Medium well     │
│ problems behind it, and how to fix them.               │ │  ── 35           │
│                                                        │ │  Lightly toasted │
│ ┌────────────────────────────────────────┐ ┌────────┐  │ │  ── 15           │
│ │ github.com/owner/repo                  │ │Scan repo│ │ │  Raw             │
│ └────────────────────────────────────────┘ └────────┘  └─┘  (idle, 0)       │
│ Try an example:  [clean-example]  [messy-example]  [famous-example]          │
│                                                                              │
│ No signup. Public repos only. Reports are public and deleted after 90 days.  │
│ ─────────────────────────────────────────────────────────────────────────── │
│ How it works (three short paragraphs in the serif; see §12.5)                │
│ Footer: Privacy · Opt out · Report a problem · Source on GitHub              │
└──────────────────────────────────────────────────────────────────────────────┘

xs (360)
┌────────────────────────┐
│ SkillIssue         ☾   │
│ How cooked             │
│ is your code?          │
│ Paste a public GitHub  │
│ repo. Get a score…     │
│ ┌────────────────────┐ │
│ │ github.com/o/r     │ │
│ └────────────────────┘ │
│ [      Scan repo     ] │
│ Try: [clean] [messy]…  │
│ (probe hidden; shown as│
│  a horizontal 5-step   │
│  legend under the form)│
└────────────────────────┘
```
Hero rationale: the characteristic thing in this subject's world is the *measuring instrument*, so the page opens with the input and the instrument, not with a stat block or gradient.

### 7.2 Scanning (`/scan/[id]`, in progress)
The probe is in **measuring** mode: neutral Probe teal fill, rising in steps with progress. Stages are a real ordered process, so numbering is appropriate here.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SkillIssue                                                          [Cancel] │
│ example/todo-app · main@3f2c9a7                                              │
│                                                                              │
│  ┌─┐   Measuring…                                                            │
│  │ │   1  Fetching code            done      3 s                            │
│  │▮│   2  Running scanners         done      21 s   (12 signals)              │
│  │▮│   3  Picking files            done      1 s    (18 files)               │
│  │▮│   4  Asking the model         running   batch 3 of 7                     │
│  └─┘   5  Scoring                  waiting                                   │
│                                                                              │
│  A scan usually takes under a minute. This page updates on its own.          │
│  If a tool fails, the report still completes and says what's missing.        │
└──────────────────────────────────────────────────────────────────────────────┘
```
Rules: rows use `aria-live="polite"` region for status; the current stage has an animated 2 px underline only while running (reduced-motion: static). Show per-stage duration when done. Cancel button (v1) is a ghost button.

### 7.3 Report (`/scan/[id]`, completed): desktop
Structure: header summary → subscores → heat map → findings master/detail.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SkillIssue                                   [Scan another repo]  ☾           │
│──────────────────────────────────────────────────────────────────────────────│
│ example/todo-app   main@3f2c9a7   scanned 2 min ago         [Copy link][Share]│
│                                                                              │
│  ┌─┐    18                                                                   │
│  │ │    Lightly toasted   ◐                                                  │
│  │▮│    A few things to fix. Start with the SQL query in server/routes/…      │
│  │▮│                                                                         │
│  └─┘    4,012 lines · TypeScript, Python · Full coverage · How is this calculated?
│──────────────────────────────────────────────────────────────────────────────│
│ Security            17   ▮▮▮░░░░░░░░░   1 high                               │
│ Bugs                13   ▮▮░░░░░░░░░░   3 medium                             │
│ Maintainability      9   ▮░░░░░░░░░░░   5 low, 2 medium                      │
│ Performance          2   ░░░░░░░░░░░░   3 low                                │
│ Repo basics         50   ▮▮▮▮▮▮░░░░░░   No tests · No CI · No license        │
│──────────────────────────────────────────────────────────────────────────────│
│ Where it's hot                                            [Map | List]       │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ server/            │ web/                              │ tests/ (none)   │ │
│ │ ┌──────┐┌─────────┐│ ┌───────────┐┌────────┐┌────────┐ │                 │ │
│ │ │users ││ auth    ││ │ Form.tsx  ││ api.ts ││…       │ │                 │ │
│ │ └──────┘└─────────┘│ └───────────┘└────────┘└────────┘ │                 │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ Legend: Raw · Lightly toasted · Medium well · Cooked · Burnt (with numbers)  │
│──────────────────────────────────────────────────────────────────────────────│
│ 12 findings   [Category ▾] [Severity ▾] [File: all ▾]   Sort: Impact ▾       │
│ ┌───────────────────────────────┬────────────────────────────────────────┐   │
│ │ ● High  Security              │ SQL query built from user input        │   │
│ │   SQL query built from user…  │ server/routes/users.ts:41–43           │   │
│ │   server/routes/users.ts:41   │ [High] [Security] [High confidence]    │   │
│ │ ● Medium Bugs                 │                                        │   │
│ │   Unhandled promise…          │  41 │ const rows = await db.query(…)   │   │
│ │ …                             │  (snippet with highlighted lines)      │   │
│ │ (list scrolls)                │                                        │   │
│ │                               │ Why it matters (serif paragraph)       │   │
│ │                               │ How to fix it (serif paragraph)        │   │
│ │                               │ [Suggest a fix]  (v1)                  │   │
│ │                               │ Helpful? [Yes][No]  [Not a real issue] │   │
│ └───────────────────────────────┴────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```
Details:
- The **summary sentence** (one line) is generated from a template using the top finding's title and file (not from the LLM), so it is always accurate.
- Subscore bars: fixed 12-step bars (each step ≈ 8.3 points) filled with the **tier color of that subscore** + outline for Toasted/Medium Well + number + word list of counts. Bars are decorative; the numbers/words carry meaning (`aria-hidden` on bars).
- The list column is 5/12, detail column 7/12; detail is `position: sticky; top: 16px` with internal scroll.

### 7.4 Report: mobile (xs)
```
┌────────────────────────┐
│ SkillIssue         ☾   │
│ example/todo-app       │
│ main@3f2c9a7 · 2m ago  │
│ ┌─┐ 18                 │
│ │▮│ Lightly toasted    │
│ └─┘ A few things to…   │
│ [Copy link] [Share]    │
│ ────────────────────── │
│ Security 17 · 1 high   │
│ Bugs 13 · 3 medium     │
│ …                      │
│ ────────────────────── │
│ Where it's hot [List]  │
│ (treemap 2-col tiles;  │
│  default to List view) │
│ ────────────────────── │
│ 12 findings [Filters]  │
│ ● High  SQL query…     │
│ ● Med   Unhandled…     │
└────────────────────────┘
Tap a finding → full-height bottom sheet (r-sheet) with the detail content.
```
- Mobile default for the heat map is **List** view (sorted by heat); Map is available.
- Filters open in a sheet with checkboxes; applied filters shown as removable chips.

### 7.5 Finding detail (panel / sheet content, top to bottom)
1. Title (`--t-h4`), file path link `file:line` (mono) → deep link to GitHub at commit SHA.
2. Chips: severity (with glyph), category, confidence ("High confidence" / "Medium confidence"), sources ("Semgrep + AI" as plain words).
3. Snippet (≤ 15 lines), highlighted range, line numbers, "Copy" button. Secrets are masked and the block shows a masked notice.
4. **Why it matters** (serif, 1–3 sentences).
5. **How to fix it** (serif, 1–3 sentences; from LLM or template).
6. Evidence line: rule id, CWE/OWASP links when known (external link icon, `rel="noopener noreferrer"`).
7. Roast line (only if level ≠ none): shown in `--ink-muted`, italic **not** used; prefixed by nothing: it is a distinct paragraph at the bottom so the serious content is read first.
8. v1: fix section (diff + verification pill + copy patch/download).
9. Feedback row: "Was this helpful?" [Yes] [No] · [Not a real issue].

Secrets: the first line of the finding's "How to fix it" is always the action ("Rotate this key now, then remove it from git history."), never a joke.

### 7.6 Fix view (v1)
```
How to fix it
  Use a parameterized query so the id can't change the SQL.
  ┌ Diff ─────────────────────────────────────────────┐
  │ - const rows = await db.query(`…${req.params.id}`)│
  │ + const rows = await db.query("… WHERE id = $1",   │
  │ +                             [req.params.id]);    │
  └───────────────────────────────────────────────────┘
  [Verified ✓]  The SQL injection rule no longer matches, and no new issues appeared.
  [Copy patch] [Download .patch]
```
Diff colors: additions/deletions use text glyphs (`+`/`−`) and line background tints derived from `--probe` (add) and `--heat-cooked` text-safe (remove) at 10% opacity, plus the glyph, so they don't rely on hue.

Verification pill copy (fixed strings):
| State | Pill | Explanation line |
|---|---|---|
| `verified` | Verified | "The scanner rule no longer matches after this change, and no new medium or higher issues appeared in the changed files." |
| `unverified` | Unverified | "No scanner covers this kind of issue, so this fix wasn't machine-checked. Review it yourself." |
| `failed` | Failed | "{reason}. Don't use this patch as is." |
| `not_run` | Not checked yet | "Verification hasn't run for this patch." |

### 7.7 History and diff (v1)
- Header: repo + tier of latest scan.
- Line chart of score over time (chart uses a single ink line; points colored by tier + outlined; y-axis reversed? **No**: keep 0 at bottom, label "Lower is better").
- Table of scans: date, commit, score, tier, findings fixed/new.
- Diff view: three groups: Fixed, New, Still open (by fingerprint).

### 7.8 Static pages
- **How scoring works:** serif prose + tables from PRD §11 (weights, tiers, worked example, "why the score can be trusted": deterministic, versioned, inputs shown).
- **About:** what it is, who made it (owner name/links; PRD Q5), how it's built (stack, honest limits), contact.
- **Privacy:** plain-language list: what is stored, for how long, no cookies, hashed IPs, analytics.
- **Opt out:** how to remove a report (file `skillissue-optout` in repo root, or email) and expected timeline.
- **404:** "No such page. Check the URL or scan a repo." + input.
- **Error boundary:** "Something broke on our side. The failure was logged." + request id + "Try again".

### 7.9 Empty, loading, error states
| State | Treatment |
|---|---|
| Report with 0 findings | Probe at ~0 (Raw). Headline "Nothing found." Body: "No scanner or model findings above the confidence threshold. That doesn't prove the code is perfect: SkillIssue only checks what it can detect." |
| Filters return none | "No findings match these filters." + [Clear filters] |
| Heat map with no supported files | "No Python, JavaScript, or TypeScript files to map." |
| Loading report | Skeleton: probe outline + gray bars; no shimmer under `prefers-reduced-motion` |
| Scan failed | Error banner (icon + code-specific message from PRD §15 + "Try another repo" input) |
| Partial coverage | Banner above findings (see §8.16) |
| Rate limited | Inline notice with the reset time in the user's locale |

---

## 8. Components

> For each: anatomy → states → behavior → accessibility. All colors via tokens. All strings from the message catalog (`messages/en.json`).

### 8.1 Button
| Variant | Style | Use |
|---|---|---|
| Primary | Fill `--probe`, text `--probe-ink`, 6 px radius, 44 px min height, 16 px text 600 | One per view (Scan repo, Suggest a fix) |
| Secondary | 1 px `--field-border`, transparent fill, `--ink` text | Copy link, Share |
| Ghost | No border, `--ink` text, underline on hover | Cancel, Clear filters |
States: default, hover (primary: darken 8%; secondary: fill `color-mix(in srgb, var(--ink) 6%, transparent)`), active (translateY 0; no bounce), focus (§6.5), disabled (opacity 0.5 + `aria-disabled`; never removes focusability when explaining a rate limit), loading (spinner replaced by text change "Scanning…", not a moving spinner if reduced motion). Minimum touch target 44×44.

### 8.2 URL input
- Single field, 56 px tall, 6 px radius, `--sheet` fill, 1 px `--field-border`; placeholder `github.com/owner/repo` in `--ink-muted`; 18 px text.
- Accepts paste of any allowed form (PRD FR-1.1). On paste, normalize display to `owner/repo` (with a subtle "Interpreted as owner/repo" caption).
- Inline validation (on blur/submit): error text below in Cooked text-safe with an icon; `aria-invalid` and `aria-describedby`.
- Enter submits. The Scan button is attached to the right on `sm+`, stacked on `xs`.
- Autofocus on Home (desktop only; not on mobile to avoid keyboard pop).

### 8.3 Example chips
Three chips below the input: text-only pills with 1 px border. Click fills the input **and** submits. `aria-label="Scan example: {name}"`.

### 8.4 The probe (signature component)
Anatomy: tube (rounded capsule), bulb, fill, four tier ticks (at 15, 35, 60, 80), tier labels on the right side of the tube (desktop) or a horizontal legend (mobile).

| Mode | Fill | Numeral | When |
|---|---|---|---|
| Idle | Empty tube; ticks visible | none | Home |
| Measuring | Neutral `--probe` fill, height = pipeline progress % | "Measuring…" text | Scan in progress |
| Result | Fill height = score %; color = tier color (+ 1.5 px ink outline for Toasted/Medium Well) | The score (`--t-score`) + tier name | Report |
| Skeleton | Outline only | none | Loading |

Sizes: hero (tube 56×360 px desktop; 40×240 px mobile), compact (16×48 px, in headers and lists).
Behavior: see §9 (the one orchestrated moment). Tick labels use the text-safe heat colors + tier names (with the score thresholds as small numbers).
Accessibility: `role="meter"`, `aria-valuemin=0`, `aria-valuemax=100`, `aria-valuenow={score}`, `aria-valuetext="18 out of 100, Lightly toasted. Lower is better."`; the numeral and tier text are real DOM text (not SVG text only).

### 8.5 Score numeral + tier
`--t-score` numeral in `--ink` (not tier-colored, to keep text contrast simple), tier name in `--t-h2`, tier glyph next to it, one-sentence summary in `--t-read` serif. Tier glyphs (lucide): Raw `snowflake`, Lightly toasted `sun`, Medium well `thermometer-sun`, Cooked `flame`, Burnt `skull`. (Glyphs are supplementary; the word is always present.)

### 8.6 Tier chip
Pill (`--r-pill`), 28 px high, fill per §4.2, text color per §4.2 "text on fill", 1.5 px ink outline when fill is Toasted/Medium Well, glyph left, tier name text. Used in header, share dialog, history table.

### 8.7 Subscore row
Grid: label (col 1–3) · number (col 4, right-aligned, tabular) · bar (col 5–9, 12 steps) · counts text (col 10–12). Label is a `<dt>`, value `<dd>` in a description list (`<dl>`). Clicking the row filters the findings by category (button semantics, `aria-pressed`).
Bar step = 8.33 points; filled steps = `ceil(score / 8.33)`; fill color = tier color for that subscore value; empty steps = `--steam`.

### 8.8 Heat map (treemap)
- Data: `report.files[]` `{path, loc, heat(0–100), findings_count}` (see ARCHITECTURE §7.10).
- Layout: `d3-hierarchy` treemap, squarified; hierarchy by directory; area ∝ LOC (files < 0.6% of total area are grouped into an "N small files" tile per directory); 2 px gaps.
- Fill = tier color for the file's heat bucket (same thresholds as tiers). Toasted/Medium Well tiles have a 1.5 px ink outline. Selected tile: 2 px `--probe` outline + 2 px offset.
- Labels: directory names as small captions top-left of each group (sans 12.8 px, sentence case). File names inside tiles when tile ≥ 88×32 px; heat number when ≥ 120×48 px. Text color per fill.
- Interaction: hover/focus tooltip "path · 320 lines · heat 64 (Cooked) · 3 findings"; click/Enter filters the findings by file (adds `?file=`), click again clears.
- **Keyboard/AT:** tiles are `<button>`s in DOM order sorted by heat desc; group `role="group" aria-label="Files by heat"`; the **List** view is the accessible equivalent and is always available via the Map/List toggle.
- Legend: five swatches with tier names and score ranges; shown once under the map.

### 8.9 Filter bar
- Category (multi-select), Severity (multi-select), File (from heat map or a searchable select), Sort (Impact default / Severity / File path). Implemented as native `<select>`/checkbox popovers for a11y; state in URL params `?category=security&severity=high,critical&file=…&sort=impact`.
- Active filters shown as chips with an × button (`aria-label="Remove filter: Severity high"`). "Clear filters" ghost button appears when any filter is active.
- Result count in a live region: "12 findings" / "3 of 12 findings".

### 8.10 Finding row (list item)
Anatomy (left→right): severity indicator · title (2 lines max, ellipsis) · category word · file:line (mono, `--ink-muted`) · confidence word (only if Medium). Selected row: 3 px left bar in `--probe` + `--sheet` fill. Hover: light ink tint.
Severity indicator: glyph + word ("High"), never a color dot alone:
| Severity | Glyph (lucide) | Color token |
|---|---|---|
| Critical | `flame` | Cooked |
| High | `octagon-alert` | Medium Well |
| Medium | `triangle-alert` | Toasted |
| Low | `circle` | Raw |
List is a `role="listbox"`-like master list implemented as buttons in a `<ul>`; ↑/↓ moves selection; Enter opens (mobile: sheet).

### 8.11 Code snippet block
Mono 14 px on `color-mix` tinted Sheet, 1 px steam border top/bottom (0 radius, flush), line numbers column, highlighted lines with 3 px left bar (severity color) + tint, horizontal scroll (never wrap), "Copy" button top-right (secondary, small). For masked secrets, the masked run is shown as `AKIA••••••••••XY` and an info line: "Secret masked. Rotate it and remove it from git history."
No syntax-highlight colors beyond two tones (keywords `--ink`, comments `--ink-muted`) to avoid competing with the heat colors.

### 8.12 Diff viewer (v1)
Unified diff, mono 14 px; `+`/`−` gutter glyphs; add/remove tints as in §7.6; file header line; "Copy patch" and "Download .patch". Collapsible if > 40 lines.

### 8.13 Verification pill (v1)
Pill with glyph + word (see §7.6 table). Verified = `--probe` outline + `check` glyph; Unverified = `--ink-muted` outline + `circle-help`; Failed = Cooked text-safe outline + `x`; Not checked = dashed outline + `minus`. The explanation line is always rendered next to it (not tooltip-only).

### 8.14 Confidence indicator
Text: "High confidence" (≥ 0.80) / "Medium confidence" (0.50–0.79) with a tooltip "How sure SkillIssue is that this is a real problem". No percentages (false precision).

### 8.15 "How is this calculated?" popover / dialog
Non-modal popover on desktop (anchored), modal dialog on mobile. Shows: overall formula in words, weights table, the five subscores with this scan's inputs, floors applied (if any), pipeline version, link to full page. Traps focus in dialog mode; closes with Esc.

### 8.16 Banners (inline, non-modal)
| Type | Icon | Text color | Example |
|---|---|---|---|
| Info | `info` | Ink | "Scanned 2 minutes ago at commit 3f2c9a7. Rescan opens in 8 minutes." |
| Warning | `triangle-alert` | Ink with Toasted text-safe icon | "ESLint didn't finish; its results are missing." |
| Reduced coverage | `triangle-alert` | Ink | "Reduced coverage: most of this repo isn't in a language SkillIssue fully supports yet." |
| Scanners only | `triangle-alert` | Ink | "The AI pass failed, so this report only includes scanner results." |
| Error | `octagon-alert` | Cooked text-safe | Scan failure messages |
Style: 10 px radius, 1 px `--steam` border, `--sheet` fill, 16 px padding, `role="status"` (info/warn) or `role="alert"` (error).

### 8.17 Toast
Bottom-center, max 1 visible, 4 s, `role="status"`, e.g., "Link copied." Action-named confirmations only; no toasts for passive events. Respect reduced motion (fade only).

### 8.18 Share dialog (v1)
Tabs: **Link** (copy), **Card** (preview 1200×630, [Download PNG]), **Badge** (preview + Markdown/HTML snippets with Copy). Focus-trapped modal, Esc to close.

### 8.19 Skeletons
Static shapes in `--steam`; a slow 1.6 s opacity pulse (0.6↔1.0) only when motion is allowed. No shimmer gradient.

### 8.20 Header and footer
- Header: wordmark left; nav right (How scoring works, About), theme toggle. Sticky only on report pages (compact). Height 56 px.
- Footer: Privacy · Opt out · Report a problem · Source on GitHub · "Automated analysis; may contain errors."

### 8.21 Theme toggle
Three states (System / Light / Dark) in a small menu; stored in `localStorage` key `si-theme`; default System. No flash: inline script sets `data-theme` before paint.

---

## 9. Motion

**Principle:** one orchestrated moment; everything else responds to a user action.

### 9.1 The orchestrated moment: "the reading"
When a scan completes and the report first renders (only on transition from the scanning view or first load of a fresh scan; not on every revisit):
1. t=0–150 ms: the measuring fill (teal) drains to 0.
2. t=150–1,350 ms: the tube fills to the score with `cubic-bezier(0.22, 1, 0.36, 1)`; fill color cross-fades from teal to the tier color at the 60% point of the animation.
3. t=1,350 ms: the numeral appears (no counting animation; counting numbers is a gimmick), tier name and summary appear with a 120 ms opacity fade.
4. The rest of the page is already present (no staggered section entrances).
Reduced motion: skip to final state immediately; no draining/filling.

### 9.2 Responsive motion (user-triggered)
| Interaction | Motion |
|---|---|
| Open finding detail (desktop) | Content swap, 120 ms opacity; no slide |
| Open bottom sheet (mobile) | Slide up 200 ms `ease-out`; scrim fade 150 ms |
| Popover open/close | 120 ms opacity + 4 px translate |
| Filter apply | Instant list update; count live-region update |
| Copy link | Button label switches to "Copied" for 2 s; toast |
| Hover states | Color/opacity only, 100 ms |

### 9.3 Progress motion
- Probe fill steps between stage percentages with 400 ms ease-out (not continuous; avoids fake precision).
- Running stage underline: 2 px line sweeping left→right, 1.4 s loop. Disabled under reduced motion (static "running" text remains).

### 9.4 Rules
- Durations: 100–200 ms for controls, ≤ 1.2 s for the reading. No bounce, no spring overshoot, no parallax, no scroll-triggered effects.
- `@media (prefers-reduced-motion: reduce)` removes all non-essential animation; essential state changes remain (instant).

---

## 10. Iconography
- Library: **lucide-react**, 20 px default, 1.75 px stroke, `currentColor`. Icons never carry meaning alone (always with text) except the theme toggle and external-link marker (which have `aria-label`s).
- Custom: the probe mark (§3.2) and tier glyph mapping (§8.5).
- Sizes: 16 (inline in text), 20 (controls), 24 (banners), 48 (empty/error illustrations: a single outlined icon, no illustrations).

---

## 11. Accessibility specification (WCAG 2.2 AA)

| Area | Requirement |
|---|---|
| Structure | One `<h1>` per page; landmarks (`header`, `nav`, `main`, `footer`); skip link "Skip to report" (visible on focus) |
| Color | Contrast per §4.3; color never the only carrier (tier/severity words + glyphs + numbers); Toasted/Medium Well fills outlined |
| Keyboard | Everything reachable/operable; logical order; roving focus in finding list and heat map; Esc closes popovers/dialogs; focus returns to the trigger |
| Focus | §6.5, never removed; focus not obscured by sticky header (use `scroll-padding-top: 72px`) |
| Targets | ≥ 44×44 px touch targets (24×24 min for dense inline controls per WCAG 2.2 target size minimum; buttons use 44) |
| Motion | Reduced-motion honored (§9); no flashing; no auto-playing loops besides the running-stage underline (disabled under reduced motion) |
| Live regions | Scan progress `aria-live="polite"`; errors `role="alert"`; filter result count polite |
| Forms | Visible labels or `aria-label`; error text linked via `aria-describedby`; no placeholder-only labeling (visually hidden label "GitHub repo URL") |
| Charts | Heat map has List alternative; history chart has a data table alternative |
| Meter | Probe semantics per §8.4 |
| Language | `lang="en"`; dates via `<time datetime>` |
| Zoom/reflow | Usable at 200% zoom and 320 px width without horizontal scroll (code/diff scroll inside their own containers) |
| Testing | axe in CI on all routes (light + dark); manual VoiceOver + NVDA pass before launch (`TASK.md` T-9.x) |

---

## 12. Copy and voice

### 12.1 Principles
1. Write from the reader's side: name things by what they understand ("your repo," "scanner," "AI review"), not by how the system is built (no "pipeline," "signals," "tokens" in UI).
2. Sentence case, active voice, plain verbs, no filler.
3. Buttons say exactly what happens ("Scan repo," "Copy link," "Suggest a fix," "Copy patch"). The same action keeps the same name everywhere ("Copy link" → toast "Link copied.").
4. Errors say what happened and what to do next. **No apologies, no exclamation marks.**
5. Empty screens invite the next action.
6. Humor lives in the roast line only; all other copy is straight.
7. Never blame the person. Never comment on skill.

### 12.2 Vocabulary (consistent terms)
| Use | Avoid |
|---|---|
| scan, report | analysis job, run |
| finding (in lists), issue/problem (in prose) | violation, signal, alert |
| scanner (deterministic tools), AI review (LLM) | pipeline, model output, LLM |
| Cooked score | badness index |
| tier | band, bucket |
| repo | repository (except in legal text) |
| fix, suggested fix | remediation |
| Verified / Unverified / Failed | Passed / Trusted / OK |
| confidence: high / medium | probability, percent |

### 12.3 Core microcopy
| Where | Copy |
|---|---|
| Home H1 | How cooked is your code? |
| Home sub | Paste a public GitHub repo. Get a score, the problems behind it, and how to fix them. |
| Input placeholder | github.com/owner/repo |
| Primary button | Scan repo |
| Home footnote | No signup. Public repos only. Reports are public and deleted after 90 days. |
| Examples label | Try an example |
| Scan stages (labels) | Fetching code · Running scanners · Picking files · Asking the model · Scoring |
| Stage status words | waiting · running · done · skipped · failed |
| Scan tip | A scan usually takes under a minute. This page updates on its own. |
| Cancel | Cancel scan |
| Report actions | Copy link · Share · Scan another repo |
| Heat map heading | Where it's hot |
| Heat map toggle | Map · List |
| Findings heading | {n} findings |
| Sort label | Sort by |
| Sort options | Impact · Severity · File |
| Finding sections | Why it matters · How to fix it |
| Feedback | Was this helpful? Yes · No · Not a real issue |
| Feedback confirm | Thanks. This helps tune the scanner. |
| Calc link | How is this calculated? |
| Cached note | Scanned {time} at commit {sha7}. Rescan opens {when}. |
| Rescan | Rescan |
| Footer disclaimer | Automated analysis; may contain errors. |
| Copy toast | Link copied. |

### 12.4 Tier copy
| Tier | Range | One-liner | Summary template |
|---|---|---|---|
| Raw | 0–14 | Barely touched by problems. | "Clean. {n} minor things found." |
| Lightly toasted | 15–34 | A few things to fix. | "A few things to fix. Start with {top_title} in {top_file}." |
| Medium well | 35–59 | Getting crispy. Prioritize the top issues. | "Getting crispy. Start with {top_title} in {top_file}." |
| Cooked | 60–79 | Serious problems. Start with the critical ones. | "Serious problems. Fix {top_title} in {top_file} first." |
| Burnt to a crisp | 80–100 | Stop shipping. Fix the security issues first. | "Stop shipping. Fix {top_title} in {top_file}, then the rest of the critical issues." |
(Summary is template-generated from the top-ranked finding, never LLM-written. If there are no findings: "Nothing found.")

### 12.5 Error and status messages (match PRD §15)
| Code | Message |
|---|---|
| `invalid_url` | That doesn't look like a GitHub repo URL. Try `owner/repo` or a full github.com link. |
| `unsupported_host` | SkillIssue only scans github.com repos for now. |
| `repo_not_found` | This repo is private or doesn't exist. SkillIssue can only scan public GitHub repos. |
| `github_rate_limited` | GitHub is limiting us right now. Try again in {n} minutes. |
| `empty_repo` | This repo has no code to scan yet. |
| `repo_too_large` | This repo is {size} MB. The limit is 150 MB. |
| `no_supported_code` | No Python, JavaScript, or TypeScript files found. Hygiene and secret checks ran; the score reflects those only. |
| `clone_failed` | Couldn't download this repo. Try again in a minute. |
| `scan_timeout` | The scan took longer than 10 minutes and was stopped. Try a smaller repo. |
| `scan_failed` | Every scanner failed on this repo. The failure was logged. |
| `rate_limited` | You've used your {n} scans for this {hour/day}. Next slot opens at {time}. Cached reports still load. |
| `budget_exhausted` | SkillIssue hit today's budget. Cached reports still work. New scans reopen at 00:00 UTC. |
| `queue_full` | Too many scans in line. Try again in a minute. |
| `repo_opted_out` | The owner of this repo asked not to be scanned. |
| `internal_error` | Something broke on our side. The failure was logged. Try again. (request id: {id}) |
| Tool warning | {Tool} didn't finish; its results are missing. |
| Scanners only | The AI pass failed, so this report only includes scanner results. |
| Reduced coverage | Reduced coverage: most of this repo isn't in a language SkillIssue fully supports yet. |

### 12.6 Roast templates (fallbacks and tone anchors)
Rule: action first for anything security-critical; roasts target the code only. The LLM may write roasts within these guardrails; if it violates them, the template below is used.

| Finding type | Gentle | Medium (default) | Unhinged |
|---|---|---|---|
| Hardcoded secret | "There's a secret in this file. Move it to an environment variable and rotate it." | "This key is committed in plain text. Rotate it before someone else finds a use for it." | "Rotate this key. Bots found it before you finished the commit message." |
| SQL injection | "This query includes user input directly. Use a parameterized query." | "This query trusts user input completely. The database has questions." | "Bold of this query to trust the entire internet." |
| `eval` on input | "Avoid `eval` on input you don't control." | "`eval` on user input is a remote control with no lock." | "This runs whatever a stranger types. It's not a feature." |
| No tests | "Adding a few tests would catch regressions early." | "No tests. Every deploy is a surprise party." | "Testing strategy: hope." |
| No README | "A README helps others use this project." | "No README. The repo is a locked door with no sign." | "The README is in the room with us. It doesn't exist." |
| No license | "Without a license, others can't legally reuse this code." | "No license. Technically nobody can use this, including you in court." | "All rights reserved by accident." |
| No CI | "CI would run your checks on every push." | "No CI. The tests, if they existed, would be run on vibes." | "Deploy pipeline: your hands." |
| `.env` committed | "A `.env` file is committed. Remove it and rotate anything inside." | "A `.env` file is committed. Congratulations, it's a public config now." | "Your `.env` is on the internet. It's basically a press release." |
| Very complex function | "This function is hard to follow. Splitting it will help." | "This function has more branches than a family tree." | "Cyclomatic complexity: yes." |
| Unhandled promise | "This async call can fail silently. Add error handling." | "If this promise rejects, nobody will know. Not even you." | "Errors go here to die quietly." |
| Vulnerable dependency | "This dependency has a known vulnerability. Update it." | "This package has a known CVE. Attackers read changelogs too." | "Your dependency has a public rap sheet." |
| Debug mode on | "Debug mode is enabled. Turn it off in production." | "Debug mode in production is a stack trace giveaway." | "Free stack traces for everyone." |
| Permissive CORS | "CORS allows every origin. Restrict it to the sites you use." | "CORS set to `*`. Everyone's invited." | "Any website may talk to your API. Cool party." |
| N+1 query | "This loop runs a query per item. Batch it." | "One query per row. The database is counting." | "1 + N queries: efficiency is a myth." |
| Empty catch | "This catch block ignores the error. Log or handle it." | "An empty catch. Bugs love a quiet place to live." | "try { everything } catch { shrug }" |

### 12.7 Page copy (drafts)
**How it works (home, three short paragraphs, serif):**
1. "SkillIssue downloads the public code from a GitHub repo and runs real scanners over it: Semgrep, Bandit, ESLint, gitleaks, and a dependency vulnerability check."
2. "An AI review reads the riskiest files, confirms or rejects what the scanners found, and explains each problem in plain language. Anything the AI reports has to point at real code, or it gets thrown out."
3. "A fixed formula turns the findings into a cooked score. The same code always gets the same score, and you can see every input."

**About (start):** "SkillIssue is a side project built to make code checkups less painful. It isn't a replacement for a security audit."

**Privacy (start):** "SkillIssue doesn't use accounts or cookies. It stores the reports it creates for 90 days, and hashed IP addresses for 30 days to limit abuse. Repo code is deleted right after each scan."

---

## 13. Assets and share formats

### 13.1 Share card (PNG 1200×630, `/api/og/[id]`)
```
┌──────────────────────────────────────────────────────────────┐
│ ▓▓▓ tier band (12 px, tier color) ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│                                                              │
│ example/todo-app                          ┌─┐                │
│ (Bricolage 700, 56 px)                    │ │  ── 80         │
│                                           │ │  ── 60         │
│ Lightly toasted                           │▮│  ── 35         │
│ (Bricolage 800 wdth 75, 120 px)           │▮│  ── 15         │
│                                           └─┘                │
│ 18 / 100  ·  lower is better              (probe 96×420)     │
│                                                              │
│ Top issues                                                   │
│  High      SQL query built from user input                   │
│  Medium    Unhandled promise rejection                       │
│  Medium    No tests found                                    │
│                                                              │
│ SkillIssue                            skillissue.example/r/… │
└──────────────────────────────────────────────────────────────┘
```
- Background `--sheet`, text `--ink`; **Burnt tier inverts**: background `#4A2A22`, text white, tier band `#CF3626`.
- Contains **no code, no file paths beyond repo name, no secrets**. Titles come from findings (secret-related titles are generic: "A live secret was committed").
- Generated with `next/og` (Satori): fonts loaded as static files (Bricolage 700/800, Source Serif not needed). Safe area 64 px. Alt text: "SkillIssue report for {repo}: {score} out of 100, {tier}."
- Also: Twitter card `summary_large_image`; OG title "{repo} is {tier} on SkillIssue".

### 13.2 Badge (SVG, 20 px high, `/badge/{owner}/{repo}.svg`)
- Two segments: left "cooked" on `--ink` bg (`#17263A`) with white text; right "{score} · {tier}" on tier fill with contrast-checked text color (§4.2).
- Font: `Verdana, "DejaVu Sans", sans-serif` 11 px (system-safe; SVG is rendered by GitHub's image proxy which cannot load web fonts).
- Width computed from text length (approx 6.5 px per char + 20 px padding).
- `role="img"` with `<title>` "Cooked score: {score}, {tier}".
- Markdown: `[![cooked score](https://skillissue.example/badge/{owner}/{repo}.svg)](https://skillissue.example/r/{owner}/{repo})`.

### 13.3 Favicons and app icons
SVG favicon (mark), 32×32 PNG fallback, 180×180 Apple touch icon (mark on Frost), `theme-color` = Frost (light) / Cellar (dark).

### 13.4 Meta
`<title>` patterns: Home "SkillIssue: how cooked is your code?" · Report "{repo}: {tier} ({score}) · SkillIssue" · Others "{Page} · SkillIssue". Meta description ≤ 155 chars. Reports `noindex` until PRD Q6 is decided.

---

## 14. Implementation handoff

### 14.1 CSS variables (`globals.css`)
```css
:root {
  --frost: #E6EDF3;  --sheet: #F5F8FA;  --ink: #17263A;  --ink-muted: #4A5B6E;
  --steam: #C5D2DD;  --field-border: #7D8FA3;
  --probe: #0B7A75;  --probe-ink: #FFFFFF;

  --heat-raw: #2B6CC4;     --heat-raw-text: #1F5FB8;
  --heat-toasted: #F0C24B; --heat-toasted-text: #7A5B00;
  --heat-medwell: #F08A24; --heat-medwell-text: #A85A0C;
  --heat-cooked: #CF3626;  --heat-cooked-text: #B3301F;
  --heat-burnt: #4A2A22;   --heat-burnt-text: #4A2A22;

  --s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 24px;
  --s-6: 32px; --s-7: 48px; --s-8: 64px; --s-9: 96px; --s-10: 128px;

  --r-2: 2px; --r-control: 6px; --r-panel: 10px; --r-sheet: 16px; --r-pill: 999px;
  --shadow-pop: 0 8px 24px rgba(23, 38, 58, 0.18);
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* dark tokens */ 
    --frost: #0F1B2B; --sheet: #172740; --ink: #E3ECF5; --ink-muted: #9DB0C4;
    --steam: #2B4160; --field-border: #7590B2; --probe: #3CC6BE; --probe-ink: #0F1B2B;
    --heat-raw-text: #6FA8EE; --heat-toasted-text: #F0C24B; --heat-medwell-text: #F5A04A;
    --heat-cooked-text: #FF7A66; --heat-burnt-text: #C98A78;
    --shadow-pop: 0 8px 24px rgba(0, 0, 0, 0.5);
  }
}
:root[data-theme="dark"] { /* same values as above */ }
html { scroll-padding-top: 72px; background: var(--frost); color: var(--ink); }
:focus-visible { outline: 2px solid var(--probe); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition-duration: 0.01ms !important; } }
```
(Duplicate the dark block for `[data-theme="dark"]` in implementation; keep it DRY via a Sass/PostCSS mixin or generated file from a `tokens.json`.)

### 14.2 Tailwind mapping (`tailwind.config.ts` excerpt)
```ts
theme: {
  extend: {
    colors: {
      frost: "var(--frost)", sheet: "var(--sheet)", ink: "var(--ink)", muted: "var(--ink-muted)",
      steam: "var(--steam)", field: "var(--field-border)", probe: "var(--probe)",
      heat: { raw: "var(--heat-raw)", toasted: "var(--heat-toasted)", medwell: "var(--heat-medwell)",
              cooked: "var(--heat-cooked)", burnt: "var(--heat-burnt)" },
    },
    fontFamily: { sans: ["var(--font-bricolage)", "ui-sans-serif", "system-ui"],
                  serif: ["var(--font-source-serif)", "ui-serif", "Georgia"],
                  mono: ["var(--font-jetbrains)", "ui-monospace", "Menlo"] },
    borderRadius: { control: "6px", panel: "10px", sheet: "16px" },
    maxWidth: { container: "1120px", read: "66ch", ui: "72ch" },
  },
}
```
Single source of truth: `apps/web/src/design/tokens.json` → generates CSS variables + Tailwind theme + the API's badge/OG color map (keeps share assets in sync).

### 14.3 Component inventory and file layout (`apps/web/src/components`)
`ui/` Button, Input, Chip, Banner, Toast, Dialog, Popover, Sheet, Tabs, Skeleton, Tooltip · `brand/` Wordmark, ProbeMark · `scan/` UrlForm, ExampleChips, StageList, Probe (hero), CancelButton · `report/` ReportHeader, TierChip, SubscoreList, HeatMap, HeatList, FilterBar, FindingList, FindingRow, FindingDetail, SeverityIndicator, ConfidenceLabel, CodeSnippet, DiffViewer, VerificationPill, CalcPopover · `share/` ShareDialog, CardPreview, BadgeSnippet · `layout/` Header, Footer, Container, ThemeToggle.

### 14.4 Design QA checklist (before each release)
- [ ] All text meets §4.3 contrast in both themes (run token contrast script).
- [ ] Toasted/Medium Well fills have outlines and labels everywhere.
- [ ] No ALL CAPS labels; no single-word headline accents; no mono outside code/paths.
- [ ] Only one orchestrated animation; reduced motion verified.
- [ ] Keyboard-only walkthrough of Home → Scan → Report → Filter → Detail → Share.
- [ ] 360 px, 768 px, 1280 px screenshots for every screen; no horizontal page scroll.
- [ ] 200% zoom check.
- [ ] Screen reader pass (VoiceOver + NVDA): meter, list, heat map alternative, live regions.
- [ ] Share card and badge render for all five tiers (light/dark card variants) with long repo names (truncate with ellipsis at 32 chars).
- [ ] Copy pass: sentence case, active voice, vocabulary table, error messages match PRD §15.
- [ ] Empty/error/partial-coverage states verified.
- [ ] Lighthouse: Performance ≥ 90 (home), Accessibility ≥ 95.

### 14.5 Open design questions
| # | Question | Default |
|---|---|---|
| DQ1 | Final font check against real renders (Bricolage width axis at 75 on small phones) | Use wdth 75 only ≥ 52 px; else wdth 90–100 |
| DQ2 | Tabular numerals availability in Bricolage; if absent, use Source Serif 4 tabular figures for numeric columns | Verify in T-7.4 |
| DQ3 | Domain and final wordmark lockup with domain | After Q3 in PRD |
| DQ4 | Whether to show repo owner avatars in the report header | Yes (small, 24 px, alt text = owner name) |
