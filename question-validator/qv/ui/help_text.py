"""Help popups of the web page: one text per page, opened with the Help button next to the page title.

Rule (2026-11-17): the page itself keeps one short line about what it is for, messages about the current state
and short captions next to a control; field explanations are `help=` tooltips; everything longer lives here.
"""

from __future__ import annotations

from qv.pipeline.priority import SIGNALS

TIERS = """
**How much a source is trusted** — **P** primary (the text itself, the official record, the author's own book) ·
**S** expert (scholarly, reputable news, official histories) · **T** encyclopaedia / summary · **X** not evidence
(quiz sites, forums). A *frame authority* is an official source of the edition's tradition (e.g. alislam.org).
"""

LEGEND = """
**Verdicts** — VERIFIED · INCORRECT · OUTDATED · CONTESTED · AMBIGUOUS · UNVERIFIED (not enough evidence; not
the same as wrong).

**Evidence for the answer** — STRONG: meets the bar for this kind of fact (e.g. the verse itself for a Qur'an
question; the official record or two independent expert sources for a record) · MODERATE: some independent
support, below the bar · WEAK: one source · NONE.

**Answer found without the key** — the evidence was read by a step that was *not told* the expected answer.
"same" is the strongest sign the answer is right; "different" is the strongest sign of an error.

**Origins (C1, C2 …)** — passages that trace back to the same source count once, however many sites repeat it.
""" + TIERS

TABLES = """
**Tables** — click a column title to sort (again = reverse, a third time = back). Longer tables have a 🔎 search
box. Click a row to open it in a popup; popups over a list have ◀ Previous / Next ▶ in the order you sorted.
"""


def signals_table() -> str:
    """The fact-heavy wording signals as a Markdown table."""
    rows = "\n".join(f"| {r} | {pts} | {m} |" for r, pts, m in SIGNALS)
    return "| Signal | Points | Meaning |\n|---|---|---|\n" + rows


#: Page → sections (title, Markdown). A page with several sections shows them as tabs in the help popup.
HELP: dict[str, list[tuple[str, str]]] = {
    "overview": [
        ("This page", """
Your question files — one per game edition — with their progress. Click a row to work on that file (or switch in
the top bar). The box below tells you, with one button, what to do next.

**✅ Ready** = questions ready for the game: 🤖 verified automatically (the checks verified them; you have not
looked) + 👍 confirmed by you + ✏️ edited by you.
"""),
        ("How it works", """
1. **Import** a question file (the game's CSV format) — its format is checked first.
2. **Validate**: choose the next batch and press *Start checking now*. The free AI limits allow a few dozen
   questions a day; when a batch stops, press it again later — or turn on the **Daily run**. Finished work is
   never repeated.
3. **Review** the results: look at what needs a person, and at any verified question you want to double-check.
   Confirm, edit, ask the specialist or remove.
4. **Export** the corrected file and copy it into the game.
"""),
        ("Top bar & tables", """
**Top bar** — the file you work on, ⓘ its details (source file, version, import date, profile) and *Eval sets*:
also list the evaluation files used to measure the validator. ⏳ shows while a batch runs.

**Menu** — « folds it into a strip of icons (hover for the page name), » opens it again.
""" + TABLES),
    ],
    "import": [
        ("Steps", """
**1 · What are you importing?** — *an update* of a file you already imported (questions with the same id and text
keep their results and decisions; only new and changed ones are checked) or *a new file* (a short name, e.g.
`world-tour`, and the edition profile: it decides the audience and, for Swab Quest and Prophets' Stories, the
Ahmadiyya understanding).

**2 · Choose the file** — a CSV in the game's format (see *File format*).

**3 · Check and import** — see *Format check*.

Terminal: `qv import file.csv --dataset world-tour`.
"""),
        ("File format", """
One question per line. Columns, in any order:

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

Required: `id`, `question`, `type`, `answer`.
"""),
        ("Format check", """
The format is checked first (no AI, nothing leaves your Mac). Every problem shows its line and what to do.
**Errors** keep those questions out of the check until you fix them and import again; **warnings** are fine.

**✨ Fix them for me** fixes what has a certain fix (encoding, spaces, column names, an answer written as text or
letter …) — ids never change; then download the fixed file for your own copy. Your original file is never changed.
"""),
    ],
    "validate": [
        ("Choosing a batch", """
Choose the next batch, then press **▶ Start checking now** — it starts right away and runs in the background; you
can close the page. This page shows its progress and log.

1. **Which questions** — all still to check, only some (category, subcategory, topic, difficulty, fact-heavy
   level) or only these ids (`1, 5, 10-12`).
2. **In which order** — as in the file, hard first, easy first, or fact-heavy wording first. Questions you edited
   always come first.
3. **How many** — suggested from today's free AI requests.

A batch stops by itself when a free limit is reached; press the button again when the limits come back. Finished
work is kept — nothing is done twice. A stopped batch is always continued first.

Terminal: `qv next <file>`. To run every day by itself, see **Daily run**.
"""),
        ("Fact-heavy wording", """
Only a way to choose the order (or a filter). It reads only the wording — no AI, no sources — and counts the kinds
of wording where quiz answers most often turn out wrong. It does **not** say how likely an answer is wrong: every
question still gets the full check. 4 points or more = high · 2–3 = medium · 0–1 = low.

{signals}
"""),
    ],
    "daily": [
        ("Daily run", """
Your Mac starts a batch every day by itself — the same as pressing *Start checking now* with **all questions still
to check, in file order** (edited questions first) — for the files you choose, in that order, until the day's free
requests are used up. It does **not** use the choices on the Validate page. If the Mac is asleep at that time, it
runs when it wakes up. Results show up in Review as usual.

Choose a time a little after the free limits reset (the page shows when).

Terminal: `qv auto status` · `qv auto on --file <name>` · `qv auto off` · `qv auto run` (run today's work now).
"""),
    ],
    "review": [
        ("Groups", """
| Group | Meaning | What you do |
|---|---|---|
| 🔍 **To review** | the sources disagree with the answer, or the question is unclear | decide |
| 🎓 **Specialist** | religious or doctrinal: needs the verse or an official Ahmadiyya source | ask your reviewer |
| ❓ **Not enough evidence** | nothing reliable was found | decide, or leave for later |
| 🎲 **Spot check** | verified, but picked at random so you can check the checker | look, then confirm |
| 🤖 **Verified automatically** | sources agree with the answer, found without seeing it | nothing |
| 👍 **Decided by you** | questions you confirmed, edited or removed | change your mind any time |
"""),
        ("Deciding", """
**Click a row** — the question opens in a popup: **📋 Result** (the result in plain words, the answer the sources
give *without* seeing yours, a suggestion and the reasons) and **📄 Sources** (one page at a time with its quotes;
*Show the quotes in their page*). Your decision is at the bottom; after it the next question opens:

- **👍 Confirm** — you checked it, it is right
- **✎ Edit** — change the question, options, answer or note (*Start from the suggestion* fills in the suggestion)
- **🎓 Specialist** — on the list for your reviewer (*List for your specialist* downloads it)
- **✖ Remove** — left out of the export
- **⏭ Later** — moves it to the end

After editing, **Check my edits again** stores the edited file as a new version; the edited questions go to the
front of the next batch. Every decision is saved with its date; the imported file is never changed.
"""),
        ("What the words mean", LEGEND),
    ],
    "export": [
        ("The files", """
**✅ Ready** = questions ready for the game: 🤖 verified automatically + 👍 confirmed by you + ✏️ edited by you.

- **Corrected file** — the whole file with your edits applied and removed questions left out; same ids, same
  order, format checked again. **This one goes into the game.**
- **Ready questions only** — only the ready questions.
- **Results report** — one line per question: result, your decision, suggestions, reasons and sources (opens in
  Excel / Numbers).

You can export at any time: open questions stay unchanged in the corrected file.

Terminal: `qv export corrected <file>` · `qv export ready <file>` · `qv export results <file>`.
"""),
        ("Into the game", """
Copy the corrected file to `game_editions/<edition>/questions.csv`, run `npm run build:content` and play a round.
The validator never writes into the game's folders itself. When you change questions in the game later, import
the file again: only new and changed questions are checked.
"""),
    ],
    "batches": [
        ("This page", """
Every batch that was run (only the current file's, unless you switch that off). Click a batch to see its
questions; click a question to see everything about it in a popup: the result, **every page that was read** (one
at a time) and the research plan with its numbers.

Terminal: `qv runs` · `qv verdict <batch> <id>` · `qv evidence <batch> <id>`.
"""),
        ("What the words mean", LEGEND),
    ],
    "files": [
        ("Files & versions", """
Every imported file and version. Click one to see its questions and its format problems. Imports are never
changed — your corrections exist only in the exports. A new version keeps the results of unchanged questions.

Terminal: `qv datasets` · `qv issues <file>` · `qv diff <file>`.
"""),
    ],
    "library": [
        ("Books as a source", """
Books are a source like websites, cited as **book + page** (e.g. *Basics of Religious Education, p. 118*). A book is
used for the editions chosen for it, and counts as an official source of the edition when its publisher is one
(alislam.org). Books stay on your Mac; exports carry only short quotes.

A book whose PDF has no usable text (e.g. the Urdu *Deeni Maloomat*) needs OCR — not built yet; it is kept but not
searched.
"""),
        ("The tabs", """
- **🔎 Search** — type words; click a result to read the whole page with your search words marked (◀ / ▶ through
  the results). For a book in another language, the machine translation helps to find the page; the evidence is
  always the original text.
- **📚 Books** — every book and its state. **➕ Add a book (PDF)** uploads one and reads it at once. Click a book to
  see it or remove it (the PDF and its pages go; quotes already used stay in the results). **🔄 Refresh** reads
  PDFs you put into the books folder yourself and listed in `config/library.yaml`.
- **🌐 Found on the web** — PDFs the research met but could not read (web PDFs are skipped). Click one to
  **download and add** it (if the site refuses, download it in your browser and use *Add a book*), or hide it.
"""),
        ("Terminal", """
`qv library status` · `qv library search "first Jalsa Salana"` · `qv library suggestions` · `qv library index`
· `qv library translate`
"""),
    ],
    "websites": [
        ("Marks", """
Which websites the checks may read and how much to trust them. Your marks count from the next batch on, on top of
the built-in list (`config/sources.yaml`). Click a site to open it and mark it:

- **✅ Use** — read it, with the trust you choose (P / S / T),
- **🔑 Needs special access** — not tried again until you clear the mark,
- **⛔ Don't use** — never read, never evidence,
- **↩ Clear my mark** — back to the built-in list.

Marks are a history: the newest one counts.
"""),
        ("The tabs", """
- **🚫 Could not be read** — sites that refused or failed.
- **⭐ Possibly good** — sites not on the built-in list that gave quotes, most first; they count as T until you
  choose.
- **📝 Your websites** — every mark, and **➕ Add a website** you know (subdomains included).

Adding a site sets how much its pages count when a search finds them; it does not make the checks search that site
on purpose (only alislam.org, alhakam.org, the Qur'an and Wikipedia are searched directly).
"""),
        ("Trust levels", TIERS),
    ],
    "usage": [
        ("Usage & quota", """
**Free quota left now** — per provider and model, what today's (or this month's) free limits still allow; 5 % of
every limit is kept unused as a safety margin. Gemini's daily limits come back at midnight Pacific time.

**Calls so far** — every call to an AI model or search service, grouped. Only free tiers are used: the cost is
always $0. Terminal: `qv quota` · `qv usage`.
"""),
    ],
}


def help_for(page: str) -> list[tuple[str, str]]:
    """The help sections of a page."""
    return [(title, text.replace("{signals}", signals_table())) for title, text in HELP[page]]
