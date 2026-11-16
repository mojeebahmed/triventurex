# Question Validator — quick guide

Check a quiz file's answers against real sources, fix what is wrong, and export a clean file for the game.
Four steps, all in the web page. Each step also has **one** command if you prefer the terminal.

## Start

Double-click **`Start Question Validator.command`** in the `question-validator` folder (or run `.venv/bin/qv ui`).
Your browser opens the validator at http://localhost:8501. Close the terminal window to stop it.

The menu on the left has four parts:

- **Overview**
- **Files** — *Import a file*
- **Check questions** — *Validate · Daily run · Review · Export*
- **Advanced** — *Batches · Files & versions · Book library · Websites · Usage & quota*

The pages that work on one question file have a bar at the top: **📄 Working on** — the file (one per game
edition: Swab Quest, World Tour, …), its source file name, version and date, and a running batch. Switch files
there, or by clicking a row on the Overview. *Eval sets* also lists the evaluation files used to measure the
validator.

The **Overview** lists every file with its progress and tells you, with one button, what to do next.

**Tables**: click a column title to sort (again = reverse, a third time = back); longer tables have a 🔎 search
box above them. **Click anywhere on a row** to open it — the details open in a **popup** over the page (close it
with ✕ or Esc). Popups that belong to a list have **◀ Previous / Next ▶**, in the order you sorted the table.
Tables are read-only — nothing in them can be changed by accident.

## 1 · Import a file

Three steps on the page: **1 · What are you importing?** — *an update of a file you already imported* (choose
which) or *a new file* (give it a short name, e.g. `world-tour`, and its edition profile). **2 · Choose the file**
(CSV). **3 · Check and import**. Terminal: `qv import file.csv --dataset world-tour`.

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

Required: `id`, `question`, `type`, `answer`. The profile decides the audience and, for Swab Quest and Prophets'
Stories, the Ahmadiyya understanding.

The format is checked first — no AI, nothing leaves your Mac. Every problem shows its line and **what to do**
(e.g. *"For multi, the answer is the number of the right option"*, or *"Your column 'Option 1' is probably
'opt_a': rename it"*). **Errors** keep those questions out of the check until you fix them and import again;
**warnings** are fine. Your original file is never changed.

**✨ Fix them for me**: when some problems have a certain fix, the page lists them first (*what will change*) and
one button fixes them all: Excel/Windows encoding, extra spaces, column names like *Correct Answer* or *Option 1*,
*Multi* → *multi*, an answer written as the option's text or letter (*Paris*, *B*) → its number, empty options
between filled ones (the answer number moves with its text). Ids never change. Then **download the fixed file**
to update your own copy, and import it. Problems that need a person (an empty answer, a comma inside a text) stay
in the list with what to do.

A new version of a file keeps every result and decision of questions that did not change — only new and changed
questions need checking.

## 2 · Validate

Choose the next batch in three steps, then press **▶ Start checking now** — the batch starts right away and runs in
the background (you can close the page; the Validate page shows its progress). Terminal: `qv next world-tour`.

1. **Which questions** — *all still to check*, *only some* (by category, subcategory, topic, difficulty or
   fact-heavy level) or *only these ids* (e.g. `1, 5, 10-12`).
2. **In which order** — as in the file (default), hard questions first, easy questions first, or *fact-heavy
   wording first*. Questions you edited always come first.
3. **How many** — the page suggests what today's free limits allow.

The list below shows exactly which questions the batch will check. **When it stops** (free limit used up, or the
internet dropped), the page says when the limits come back; press the button again then — finished work is kept,
nothing is done twice. A stopped batch is always continued first.

*Fact-heavy wording* (explained at the bottom of the page) counts kinds of wording where quiz answers most often go
wrong — numbers and dates, "most / first / only" claims, facts that can go out of date, references and quotes,
notes with their own claims. It reads only the wording (no AI); it is **only a way to choose the order** (or a
filter), **not** a prediction that an answer is wrong.

## ⏰ Daily run

Its own page under *Check questions*: choose the files and a time, press *Save and turn on*. Your Mac then starts
a batch every day — **all questions still to check, in file order** (not the choices on the Validate page) — file
after file, until the day's free requests are used up; if the Mac is asleep, it runs when it wakes up. Turn it
off on the same page. Terminal: `qv auto on --file swab-quest --file prophets-stories`, `qv auto status`,
`qv auto off`, `qv auto run` (do today's work now).

How long it takes: about 25 questions a day for free, so Swab Quest (432 questions) takes about two and a half
weeks of daily batches. It costs nothing.

## 3 · Review the results

The Review page lists **every checked question** in a table — including the verified ones, so you can look at
the sources behind any result. Buttons above the table show one group at a time:

| Group | Meaning | What you do |
|---|---|---|
| 🤖 **Verified automatically** | sources agree with the answer, found without seeing it | nothing |
| 🔍 **To review** | the sources disagree with the answer, or the question is unclear | decide |
| 🎓 **For a specialist** | religious or doctrinal: needs the verse or an official Ahmadiyya source | ask your reviewer |
| ❔ **Not enough evidence** | nothing reliable was found | decide, or leave for later |
| 🎲 **Spot check** | verified, but picked at random so you can check the checker | look, then keep |
| 👍 **Decided by you** | questions you confirmed, edited or removed | change your mind any time |

Search or filter by category, then **click a row**: the question opens in a popup. **📋 Result** shows the result
in plain words, what the sources say, the answer they give **without** seeing yours, a suggestion and the reasons;
**📄 Sources** shows the pages one at a time (◀ Previous / Next ▶) with their quotes, and *Show the quotes in
their page*. Your decision is at the bottom of the popup — press one button and the next question opens by itself
(close the popup to see the updated list):

- **👍 Confirm** — you checked it, it is right
- **✎ Edit** — change the question, options, answer or note (*Start from the suggestion* fills in the suggestion)
- **🎓 Specialist** — moves it to the specialist group; **Download the list for your specialist** gives
  them a sheet with the questions, reasons and sources. When they answer, open the question and keep or edit it.
- **✖ Remove** — leave it out of the export
- **⏭ Later** — skip for now (it moves to the end)

After editing, **Check my edits again** stores the edited file as a new version; the edited questions then go to
the front of the next batch. You can also export without re-checking. Every decision is saved with its date
(*Decided* group); you can change it at any time, and the imported file itself is never changed.

## 4 · Export

**✅ Ready** (on the Overview and Export pages) = questions ready for the game:

- 🤖 **verified automatically** — the checks verified them; you have not looked at them,
- 👍 **confirmed by you** — you looked and pressed *Confirm*,
- ✏️ **edited by you**.

Download one of three files (terminal: `qv export corrected world-tour`, `… ready …`, `… results …`):

- **Corrected file** — the whole file with your edits applied and removed questions left out, same ids and order,
  format checked again. This is the one for the game.
- **Ready questions only** — just the ready questions (the three kinds above, the page shows each number).
- **Results report** — one line per question: result, your decision, suggestions, reasons and sources (opens in
  Excel / Numbers).

Then copy the corrected file to `game_editions/<edition>/questions.csv`, run `npm run build:content` and play a
round. The validator never writes into the game's folders itself. When you change questions in the game later,
import the file again: only new and changed questions are checked.

## For power users

Everything above also works with commands: `qv status` (where every file stands) and the full set in
`qv --help` — `research`, `validate`, `judge`, `resume`, `runs`, `verdicts`, `verdict`, `evidence`, `metrics`,
`usage`, `quota`, `issues`, `diff`, `export`, `eval …`. The **Advanced** pages in the browser have the detailed
views: **Batches** (every batch; a question opens with its result, every page that was read and the research
plan), **Files & versions** (imports, their questions and format problems), **Book library**, **Websites** and
**Usage & quota**. What is
stored and how to look inside the database: [DATABASE.md](DATABASE.md). How a verdict is reached:
[METHODOLOGY.md](METHODOLOGY.md).

## Book library

Books are a source like websites, cited as **book + page** (e.g. *Basics of Religious Education, p. 118*). They
are used for the editions listed for each book — today Swab Quest and Prophets' Stories — and count as an official
Ahmadiyya source when their publisher is (alislam.org).

The **Book library** page (Advanced) has three parts:

- **Books** — every book with its state. **➕ Add a book (PDF)**: upload the file, give its title, author, language,
  publisher, trust and editions; it is read at once. Click a book to see it or **remove** it (the PDF and its pages
  go; quotes already used stay in the results). Books added on the page are listed in
  `data/library/books.yaml` (yours, not in git); `config/library.yaml` keeps the built-in list.
- **Books found on the web** — PDFs the research met but could not read (e.g. *Life of the Promised Messiah*). Click
  one: **⬇ Download and add** fetches it and adds it like an upload (if the site refuses, download it in your
  browser and use *Add a book*), or **🙈 Not a book for the library** hides it.
- **Search the books** — type words; the results table shows where each page matches. Click a result: the whole
  page opens with your **search words marked**, with ◀ Previous / Next ▶ through the results.

Terminal: `qv library index` (after putting a PDF in `data/library/` and listing it in `config/library.yaml` by
hand), `qv library status`, `qv library search "first Jalsa Salana"`, `qv library suggestions`.

**Books in another language** (the German *Dieni Ma'loomat*): add `translate_for_search: en` to the book in
`library.yaml` and run `qv library translate`. Every page gets a machine translation into English, so English
questions find the page. The translation is only for finding: the quote and the citation are always the original
page. It uses the free Flash-Lite requests (one per page) and continues the next day if they run out.

Books stay on your Mac; exports only carry short quotes.

## Websites

The **Websites** page (Advanced) decides which sites the checks may read and how much to trust them. Your marks
count from the next batch on, on top of the built-in list (`config/sources.yaml`).

- **🚫 Could not be read** — sites that refused (e.g. britannica.com, 403) or failed. Open one, look at it in your
  browser, then mark it **🔑 needs special access** (not tried again until you clear the mark), **⛔ don't use**
  (never read, never evidence) or **✅ use** with the trust you choose.
- **⭐ Possibly good** — sites not on the built-in list that gave quotes (e.g. ahmadipedia.org), most quotes first.
  They count as T (encyclopaedia / summary) until you choose a better trust or mark them *don't use*.
- **📝 Your websites** — **➕ Add a website** you know (address or domain; subdomains included) with its trust, and see or
  change every mark. Adding a site sets how much its pages count when a search finds them; it does not make the
  checks search that site on purpose.

Click a site to open it in a popup with the mark buttons; each tab has a search box. Marks are a history like
your review decisions: the newest one counts, **↩ Clear my mark** goes back to the
built-in list.

## Not built yet

- How far *Verified* can be trusted is still being measured on the evaluation set (a few days of free quota).
- **Urdu books** whose PDF has no usable text (e.g. *Deeni Maloomat*) need OCR (text recognition) — not yet.
