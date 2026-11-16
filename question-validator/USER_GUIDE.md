# Question Validator — quick guide

Check a quiz file's answers against real sources, fix what is wrong, and export a clean file for the game.
Four steps, all in the web page. Each step also has **one** command if you prefer the terminal.

> **Status (2026-11-16):** this guide describes the simple workflow being built. Steps marked
> 🟢 work today, 🟡 work today with a longer command, ⚪ are not built yet. The plan is at the end.

## Start

Double-click **`Start Question Validator.command`** in the `question-validator` folder ⚪
— or run `.venv/bin/qv ui` 🟢. Your browser opens the validator at http://localhost:8501.

The page shows four steps: **1 Import · 2 Validate · 3 Review · 4 Export**, and a card telling you what to do next.

## 1 · Import a file

Drop a CSV file on the page ⚪ (terminal: `qv import file.csv --dataset swab-quest` 🟢).

The file needs these columns (the game's format), in any order:

| Column | What goes in it |
|---|---|
| `id` | a number; never changes, never reused |
| `question` | the question |
| `type` | `multi` (four options) or `open` (free answer) |
| `answer` | for `multi`: the right option's number 1–4; for `open`: the answer text |
| `opt_a` … `opt_d` | the four options (empty for `open`) |
| `difficulty` | `easy` or `hard` |
| `category`, `subcategory`, `topic` | where it belongs |
| `note` | optional: the explanation shown after answering |

Required: `id`, `question`, `type`, `answer`. Choose the edition (it decides the audience and, for Swab Quest and
Prophets' Stories, the Ahmadiyya understanding).

The validator checks the format first — no AI, nothing leaves your Mac:

- **Errors** (must be fixed before it can be used): missing column, unknown type, answer not 1–4, duplicate id …
- **Warnings** (can be imported): near-duplicate questions, fewer than four options, extra spaces …

Each problem shows its line and **a suggested fix** ⚪ (today: the problem only 🟢). Simple ones (extra spaces,
line endings, answer written as the option text instead of its number) can be fixed with one click, which gives
you a corrected copy to download — your original file is never changed ⚪.

When the file is imported, the next-step card says **"Validate the first batch"**.

## 2 · Validate

Click **Validate next batch** ⚪ (terminal: `qv next swab-quest` ⚪; today `qv validate swab-quest --ids 1-25` 🟡).

- It works through the questions in order, as many as today's free limits allow, and you can close the page.
- **When it stops** (the free daily limit is used up, or the internet dropped), the card says so and when to come
  back. Click the same button again — finished work is kept, nothing is paid for twice. That is all you ever do
  in this step.
- Optional: **Continue automatically every day** ⚪ runs the next batch each morning on its own.

How long it takes: the free AI limits allow roughly **25 questions a day**, so Swab Quest (432 questions) takes
about two and a half weeks of daily batches. It costs nothing.

## 3 · Review the results

Each question ends in one of four groups:

| Group | Meaning | What you do |
|---|---|---|
| ✅ **Verified** | sources agree with the answer, found without seeing it | nothing (a few are shown for spot checks) |
| 🔍 **To review** | the sources disagree with the answer, or the question is unclear | decide |
| 🎓 **For a specialist** | religious or doctrinal: needs the verse or an official Ahmadiyya source | send to your reviewer |
| ❔ **Not enough evidence** | nothing reliable was found | decide, or leave for later |

The review page shows one question at a time ⚪ (today: read-only in the web page 🟢, `qv verdict <run> <id>` 🟢):
the verdict in plain words, the answer the sources give, the quotes with links to their pages, and a suggestion.
Pick one:

- **Keep as is** — you checked it, it is right
- **Use the suggestion** — take the suggested answer or wording
- **Edit** — change the question, options, answer or note yourself
- **Ask the specialist** — goes on a printable list for your reviewer; their answer is entered later
- **Remove** — leave the question out of the export
- **Later** — skip for now

Edited questions are checked again in the next batch ⚪. Every decision is saved with the date; the imported
file itself is never changed.

## 4 · Export

Click **Download corrected file** ⚪ (terminal: `qv export corrected swab-quest --changes approved.json` 🟡).

- **Corrected file** — the whole file with only your approved changes applied, same order and ids, and checked again
  for format errors before you get it.
- **Verified only** — just the questions that were verified or that you approved ⚪.
- **Report** — one line per question: result, sources, your decision 🟡 (`qv export report` covers format only).

Then copy the file to `game_editions/<edition>/questions.csv` and run `npm run build:content` as usual. The validator
never writes into the game's folders itself.

**Later:** after you edit questions in the game, import the file again — only new and changed questions are
validated ⚪.

## For power users

Everything above also works with the full command set (`qv --help`): `research`, `validate`, `judge`, `resume`,
`runs`, `verdicts`, `verdict`, `evidence`, `metrics`, `usage`, `quota`, `issues`, `diff`, `export`, `eval …`.
What is stored and how to look inside the database: [DATABASE.md](DATABASE.md). How a verdict is reached:
[METHODOLOGY.md](METHODOLOGY.md).

---

## What still has to be built (plan)

In this order; each is a separate branch, tested, and tried in the browser before merging.

1. **`qv next` + Validate button + progress card** — next batch sized to today's free quota, continues a stopped
   batch automatically, skips questions already validated with the same text; runs in the background so the page
   can close; the card shows done / to review / remaining and when the free limits reset.
2. **Review page + decisions** — the one-question-at-a-time queue with the six actions, an append-only
   decisions table (latest decision wins), the specialist list (printable / CSV), re-checking edited questions.
3. **Export page** — corrected file built from the decisions, verified-only file, full results report.
4. **Import page** — upload, format check with a suggested fix per problem, one-click fixes as a corrected copy,
   column-name matching for files from elsewhere.
5. **Small comforts** — the double-click start file, optional daily automatic batch, re-import validates only
   changed questions.

Running alongside: the eval measurement (a few days of free quota) — it tells us how far *Verified* can be
trusted before you rely on step 3's "nothing to do".
