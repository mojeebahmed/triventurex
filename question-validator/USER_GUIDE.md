# Question Validator — quick guide

Check a quiz file's answers against real sources, fix what is wrong, and export a clean file for the game.
Four steps, all in the web page. Each step also has **one** command if you prefer the terminal.

## Start

Double-click **`Start Question Validator.command`** in the `question-validator` folder (or run `.venv/bin/qv ui`).
Your browser opens the validator at http://localhost:8501. Close the terminal window to stop it.

The sidebar shows:

- **Working on** — the question file you are working on, with its source file name, version and date. You can
  import one file per game edition (Swab Quest, World Tour, …) and switch between them here.
- The menu: **Overview · 1 Import · 2 Validate · 3 Review · 4 Export**, and **Advanced** for the detailed views.

The **Overview** lists every file with its progress (click a row to work on that file) and tells you, with one
button, what to do next. In every table, **click a row** to open it; the open row is highlighted.

## 1 · Import a file

Drop a CSV file on the page and choose **a new file** (give it a short name, e.g. `world-tour`, and its edition
profile) or **a new version of an existing file**. Terminal: `qv import file.csv --dataset world-tour`.

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

A new version of a file keeps every result and decision of questions that did not change — only new and changed
questions need checking.

## 2 · Validate

Press **Validate next batch**. Terminal: `qv next world-tour`.

- It checks the next questions in the order you choose, as many as today's free limits allow (about 25 a
  day). You can close the page while it works; the Validate page shows its progress.
- **When it stops** (free limit used up, or the internet dropped), the page says when the limits come back.
  Press the same button again then — finished work is kept, nothing is done twice. That is all you do in this
  step.
- **Choose which questions** (optional): by category, subcategory, topic and difficulty.
- **Order**: as in the file (default), hard questions first, easy questions first, or *fact-heavy wording first*.
  Questions you edited always come first.
- *Fact-heavy wording* (its own tab) counts kinds of wording where quiz answers most often go wrong — numbers and
  dates, "most / first / only" claims, facts that can go out of date, references and quotes, notes with their own
  claims. It reads only the wording (no AI); it is **not** a prediction that an answer is wrong, it only changes the
  order. The tab lists every signal and its points.

How long it takes: about 25 questions a day for free, so Swab Quest (432 questions) takes about two and a half
weeks of daily batches. It costs nothing.

## 3 · Review the results

The Review page lists **every checked question** in a table — including the verified ones, so you can look at
the sources behind any result. Buttons above the table show one group at a time:

| Group | Meaning | What you do |
|---|---|---|
| ✅ **Verified** | sources agree with the answer, found without seeing it | nothing |
| 🔍 **To review** | the sources disagree with the answer, or the question is unclear | decide |
| 🎓 **For a specialist** | religious or doctrinal: needs the verse or an official Ahmadiyya source | ask your reviewer |
| ❔ **Not enough evidence** | nothing reliable was found | decide, or leave for later |
| 🎲 **Spot check** | verified, but picked at random so you can check the checker | look, then keep |
| 👍 **Decided by you** | questions you kept, edited or removed | change your mind any time |

Search or filter by category, then **click a row**: below the table you see the result in plain words, what the
sources say, the answer they give **without** seeing yours, a suggestion, the reasons and the quotes with links.
Then press one button (after it, the next question opens by itself):

- **✔ Keep** — you checked it, it is right
- **✎ Edit** — change the question, options, answer or note (*Start from the suggestion* fills in the suggestion)
- **🎓 Specialist** — moves it to the specialist group; **Download the list for your specialist** gives
  them a sheet with the questions, reasons and sources. When they answer, open the question and keep or edit it.
- **✖ Remove** — leave it out of the export
- **⏭ Later** — skip for now (it moves to the end)

After editing, **Check my edits again** stores the edited file as a new version; the edited questions then go to
the front of the next batch. You can also export without re-checking. Every decision is saved with its date
(*Decided* group); you can change it at any time, and the imported file itself is never changed.

## 4 · Export

Download one of three files (terminal: `qv export corrected world-tour`, `… verified …`, `… results …`):

- **Corrected file** — the whole file with your edits applied and removed questions left out, same ids and order,
  format checked again. This is the one for the game.
- **Verified only** — just the questions that were verified or that you kept or edited.
- **Results report** — one line per question: result, your decision, suggestions, reasons and sources (opens in
  Excel / Numbers).

Then copy the corrected file to `game_editions/<edition>/questions.csv`, run `npm run build:content` and play a
round. The validator never writes into the game's folders itself. When you change questions in the game later,
import the file again: only new and changed questions are checked.

## For power users

Everything above also works with commands: `qv status` (where every file stands) and the full set in
`qv --help` — `research`, `validate`, `judge`, `resume`, `runs`, `verdicts`, `verdict`, `evidence`, `metrics`,
`usage`, `quota`, `issues`, `diff`, `export`, `eval …`. The **Advanced** page in the browser has the detailed
views (every source and quote of a question, files and format problems, batches, quota and usage). What is
stored and how to look inside the database: [DATABASE.md](DATABASE.md). How a verdict is reached:
[METHODOLOGY.md](METHODOLOGY.md).

## Not built yet

- **One-click fixes** on import (e.g. remove extra spaces, turn an answer written as text into its option
  number) — today the page tells you what to change in the file.
- **Continue automatically every day** — today you press *Validate next batch* (or run `qv next`) once a day.
- How far *Verified* can be trusted is still being measured on the evaluation set (a few days of free quota).
