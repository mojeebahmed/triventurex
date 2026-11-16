"""Web page (Streamlit). Run with `qv ui`, or double-click `Start Question Validator.command`.

Menu (sidebar, in sections): Overview · Files: Import · Check questions: Validate, Daily run, Review, Export ·
Advanced: Batches, Files & versions, Book library, Websites, Usage & quota. The file being worked on is chosen in
the bar at the top of the pages that work on one file. Queries and writes live in qv.services; this file only lays
them out. Long work (a batch) runs as a separate `qv next` process, so the page can be closed while it works.

Every table goes through `data_table` (our own component in qv/ui/table.py) so all tables look and behave the
same: header stays put, sort by clicking a header, optional search box, click a row to open it — details open in
a popup (`st.dialog`) rather than under the table.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable

import pandas as pd
import streamlit as st

from qv.config import Settings, available_profiles, load_profile, load_research_config
from qv.db.session import Database
from qv.services import views, worker, workflow
from qv.services.workflow import STATUS_LABEL
from qv.ui.help_text import help_for
from qv.ui.table import render_table

st.set_page_config(page_title="Question Validator", page_icon="✅", layout="wide")

ROW_PX, HEADER_PX = 35, 36
CSS = """
<style>
[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] { font-weight: 700; letter-spacing: .02em; }
[data-testid="stSidebarNav"]::before { content: "✅ Question Validator"; display: block; font-size: 1.25rem;
  font-weight: 700; padding: 0 0 0.8rem 0.6rem; }
/* Collapsed menu = a narrow strip of icons; the page name shows as a tooltip on hover */
section[data-testid="stSidebar"][data-collapsed="true"] { transform: none !important; width: 56px !important;
  min-width: 56px !important; max-width: 56px !important; }
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarContent"],
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarNav"],
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarNavItems"] { overflow: visible !important; }
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarNav"] { padding-top: 3.2rem; }
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarNav"]::before,
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarUserContent"],
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarHeader"] { display: none !important; }
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stNavSectionHeader"] { height: 1px;
  overflow: hidden; color: transparent; background: rgba(49, 51, 63, 0.15); margin: 0.5rem 0.6rem; padding: 0; }
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarNavLink"] { position: relative;
  justify-content: center; padding: 0.45rem 0; margin: 0.1rem 6px; }
/* « / » sit inside the menu, at its top: « always visible when open, » on the icon strip when closed */
[data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; opacity: 1 !important; }
body:has(section[data-testid="stSidebar"][data-collapsed="true"]) [data-testid="stHeader"] { z-index: 1000003; }
[data-testid="stExpandSidebarButton"] { position: fixed !important; left: 0; top: 0; width: 56px; height: 60px;
  justify-content: center; align-items: center; border-radius: 0; background: rgb(248, 248, 247) !important; }
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarNavLink"] > span[label] {
  display: none; }
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarNavLink"]:hover > span[label] {
  display: block; position: absolute; left: 50px; top: 50%; transform: translateY(-50%); z-index: 1000001;
  background: #31333f; color: #fff; padding: 3px 10px; border-radius: 6px; white-space: nowrap; font-size: 0.85rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2); pointer-events: none; }
section[data-testid="stSidebar"][data-collapsed="true"] [data-testid="stSidebarNavLink"]:hover > span[label] p {
  color: #fff; margin: 0; }
/* "Working on" sits in the app's top bar (right side), taking no room on the page */
.st-key-qv_header { position: fixed; top: 0.55rem; right: 3.6rem; z-index: 1000004; width: auto !important; }
.st-key-qv_header [data-testid="stSelectbox"] { min-width: 190px; }
[data-testid="stMainBlockContainer"] { padding-top: 3.6rem; }
mark { background: #ffe066; padding: 0 2px; border-radius: 3px; }
.qv-page { white-space: pre-wrap; font-size: 0.92em; line-height: 1.5; max-height: 55vh; overflow: auto;
  border: 1px solid rgba(49, 51, 63, 0.15); border-radius: 8px; padding: 0.75rem; }
.qv-quote { border-left: 4px solid #ffcd3c; padding: 0.3rem 0.8rem; margin: 0.4rem 0 0.1rem 0;
  background: rgba(255, 205, 60, 0.08); border-radius: 0 6px 6px 0; }
</style>
"""

STATUS_ICON = {"to_review": "🔍", "specialist": "🎓", "no_evidence": "❓", "spot_check": "🎲", "verified": "🤖",
               "approved": "👍", "edited": "✏️", "removed": "✖️", "in_progress": "⏳", "failed": "⚠️",
               "not_checked": "▫️", "format_error": "🛑"}
TIER_LABEL = {"P": "P · primary source", "S": "S · expert source", "T": "T · encyclopaedia / summary",
              "X": "X · not evidence"}
STATUS_TEXT = {"extracted": "read", "excluded": "not used", "failed": "could not be read", "pending": "not read yet"}
VERDICT_TEXT = {
    "VERIFIED": "strong, independent evidence supports the expected answer, and reading the evidence without the "
                "key gives the same answer.",
    "INCORRECT": "strong evidence contradicts the expected answer or something the question takes for granted.",
    "OUTDATED": "the answer was true once, but the evidence shows it has changed.",
    "CONTESTED": "good sources disagree; no side clearly outweighs the other.",
    "AMBIGUOUS": "as worded, more than one answer can be defended (or it depends on a definition the question "
                 "does not give).",
    "UNVERIFIED": "not enough evidence to confirm the answer — this does not mean it is wrong.",
}
GROUP_LABEL = {"all": "All checked", "to_review": "🔍 To review", "specialist": "🎓 Specialist",
               "no_evidence": "❓ Not enough evidence", "spot_check": "🎲 Spot check",
               "verified": "🤖 Verified automatically", "decided": "👍 Decided by you"}
GROUP_HELP = {
    "all": "Every question that has been checked, whatever the result.",
    "to_review": "The sources disagree with the answer, or the question is unclear. Decide what to do.",
    "specialist": "Religious or doctrinal: needs the verse or an official Ahmadiyya source. Download the list "
                  "for your reviewer, then enter their answer here.",
    "no_evidence": "Nothing reliable was found. Confirm it if you know it is right, edit it, or leave it for later.",
    "spot_check": "Verified automatically; a few are picked at random so you can check the checker.",
    "verified": "Verified automatically by the checks — you have not looked at them. Open any of them to look at "
                "the sources the result rests on.",
    "decided": "Questions you decided (confirmed, edited or removed). Open one to see or change your decision.",
}
READY_HELP = ("Ready for the game = 🤖 verified automatically + 👍 confirmed by you + ✏️ edited by you. "
              "These are the questions in the *Ready questions only* download.")


@st.cache_resource
def get_db() -> Database:
    """One database handle per server process."""
    return Database(Settings().database_url)


db = get_db()
settings = Settings()


# --- shared pieces ------------------------------------------------------------------------

def data_table(rows: list[dict] | pd.DataFrame, *, key: str | None = None, select: bool = False,
               columns: dict | None = None, max_rows: int = 12, highlight: int | None = None,
               search: bool | str | None = None,
               on_open: Callable[[int, list[int]], None] | None = None) -> int | None:
    """Every table on the page: same look, height that fits, row count, sortable columns, optional search box.

    - `search`: True / a placeholder text shows a search box above the table (default: when it has > 8 rows).
    - `select=True`: a click on a row picks it; returns the picked position (in `rows`), else None.
    - `on_open(row, order)`: called once per click (also a second click on the same row) — for opening a popup.
      `order` = the rows as the viewer saw them (after their sort and search), for Previous / Next in the popup.
    """
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if df.empty:
        st.caption("Nothing to show.")
        return None
    if search is None:
        search = len(df) > 8
    placeholder = search if isinstance(search, str) else ("🔎 Search this table …" if search else "")
    select = select or on_open is not None
    shown = min(len(df), max_rows)
    row, nonce, order = render_table(df, key=key, select=select, columns=columns,
                                     height=HEADER_PX + ROW_PX * shown + 16,  # + room for a sideways scrollbar
                                     highlight=highlight, search=placeholder)
    note = f"{len(df)} row{'s' if len(df) != 1 else ''}"
    if len(df) > max_rows:
        note += " — scroll to see all"
    if select:
        note += " · click a row to open it"
    note += " · click a column title to sort"
    st.caption(note)
    if on_open is not None and row is not None and nonce is not None and key:
        seen = f"_seen_{key}"
        if st.session_state.get(seen) != nonce:
            st.session_state[seen] = nonce
            on_open(row, order or list(range(len(df))))
    return row


TEXT = st.column_config.TextColumn
NUM = st.column_config.NumberColumn
COLS_QUESTION = {"question": TEXT("Question", width="large"), "answer": TEXT("Answer", width="medium"),
                 "category": TEXT("Category", width="medium"), "id": TEXT("Id", width="small"),
                 "status": TEXT("Status", width="medium"), "difficulty": TEXT("Difficulty", width="small"),
                 "level": TEXT("Level", width="small"), "points": NUM("Points", width="small"),
                 "result": TEXT("Result", width="small"), "your decision": TEXT("Your decision", width="small")}


def path(*parts: str) -> str:
    """category > subcategory > topic"""
    return " > ".join(p for p in parts if p)


def status_text(s: workflow.QuestionState) -> str:
    """Status with its icon."""
    return f"{STATUS_ICON[s.status]} {STATUS_LABEL[s.status]}"


def highlight(text: str, passages: list[dict], context: int = 400) -> str:
    """HTML excerpts of a document around each grounded passage, the passage marked."""
    parts = []
    for p in passages:
        a, b = p["start"], p["end"]
        lo, hi = max(0, a - context), min(len(text), b + context)
        parts.append(f"<p style='font-size:0.9em'>…{html.escape(text[lo:a])}"
                     f"<mark>{html.escape(text[a:b])}</mark>{html.escape(text[b:hi])}…</p>")
    return "<hr>".join(parts)


def mark_words(text: str, words: list[str]) -> str:
    """HTML of `text` with every search word marked (whole words and word starts, any case)."""
    out = html.escape(text)
    if not words:
        return out
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")",
                         re.IGNORECASE)
    return pattern.sub(r"<mark>\1</mark>", out)


def snippet(text: str, words: list[str], width: int = 90) -> str | None:
    """A short piece of `text` around the first search word (for a table cell); None when no word is in it."""
    low = text.lower()
    found = [i for w in words if (i := low.find(w)) >= 0]
    if not found:
        return None
    at = min(found)
    lo = max(0, at - width // 3)
    while 0 < lo < at and not text[lo - 1].isspace():      # start at a word
        lo += 1
    hi = min(len(text), at + width)
    return ("…" if lo else "") + " ".join(text[lo:hi].split()) + ("…" if hi < len(text) else "")


def page_title(title: str, help_key: str, intro: str | None = None) -> None:
    """The page title with a Help button (opens the page's help in a popup) and an optional one-line intro."""
    c = st.columns([6, 1], vertical_alignment="center")
    c[0].title(title)
    if c[1].button("Help", icon=":material/help:", key=f"help_{help_key}", type="tertiary",
                   help="What this page is for and how it works"):
        help_dialog(help_key)
    if intro:
        st.caption(intro)


@st.dialog("Help", width="large")
def help_dialog(key: str) -> None:
    """The help text of one page."""
    st.markdown(help_for(key))


def current() -> str:
    """The file being worked on, or stop with a pointer to Import."""
    name = st.session_state.get("dataset")
    if not name:
        st.info("Import a question file first.")
        if st.button("Go to Import", type="primary"):
            st.switch_page(PAGES["import"])
        st.stop()
    return name


def progress(states: list[workflow.QuestionState]) -> dict[str, int]:
    """Progress bar for a file; returns the counts."""
    c = workflow.counts(states)
    checkable = len(states) - c["format_error"]
    done = checkable - c["not_checked"] - c["failed"] - c["in_progress"]
    st.progress(done / max(checkable, 1), text=f"{done} of {checkable} questions checked"
                + (f" ({c['format_error']} with format errors are skipped)" if c["format_error"] else ""))
    return c


def ready(c: dict[str, int]) -> int:
    """Questions ready for the game."""
    return sum(c[k] for k in workflow.READY_STATUSES)


def next_step(name: str) -> None:
    """What to do next for a file: one sentence and one button."""
    c = workflow.counts(workflow.question_states(db, name))
    left = c["not_checked"] + c["failed"] + c["in_progress"]
    review = sum(c[k] for k in workflow.REVIEW_STATUSES)
    b = worker.status(settings.data_dir)
    if b.running and b.dataset == name:
        st.info("⏳ A batch is being checked right now. You can close this page and come back later.")
        target, label = "validate", "See progress"
    elif review:
        st.warning(f"👉 **Next: review {review} question(s)** that need a person.")
        target, label = "review", "Go to Review"
    elif left:
        st.info(f"👉 **Next: validate the next batch** — {left} question(s) still to check.")
        target, label = "validate", "Go to Validate"
    else:
        st.success("👉 **Everything is checked and decided.** Download the corrected file.")
        target, label = "export", "Go to Export"
    if st.button(label, type="primary", key=f"next_{target}"):
        st.switch_page(PAGES[target])


def verdict_box(v: dict) -> None:
    """The result of one question in plain words."""
    box = {"VERIFIED": st.success, "INCORRECT": st.error, "OUTDATED": st.error}.get(v["verdict"], st.warning)
    box(f"**{v['verdict']}** — {VERDICT_TEXT[v['verdict']]}"
        + (f" Problem is in the **{v['defect_location'].replace('_', ' ')}**." if v["defect_location"] else ""))
    blind = {True: "same as the answer", False: "**different** from the answer", None: "—"}[v["blind_matches_key"]]
    st.markdown(f"Evidence for the answer: **{v['evidence_strength']}** · Found without the key: {blind} · "
                f"Question quality: **{(v['question_quality'] or '—').replace('_', ' ').lower()}** · "
                f"Next step: **{v['review_status'].replace('_', ' ')}**")
    st.markdown(f"**{v['evidence_summary']}**")
    if v["blind_status"]:
        st.markdown("Read **without** knowing the answer, the sources say: "
                    f"*{v['blind_answer'] or v['blind_status'].replace('_', ' ')}*")
    if v["suggested_answer"]:
        st.markdown(f"💡 Suggested answer: **{v['suggested_answer']}**")
    if v["suggested_question"]:
        st.markdown(f"💡 Suggested question: **{v['suggested_question']}**")


def source_viewer(run_id: int, question_id: int, key: str, *, all_pages: bool = False,
                  detail: dict | None = None) -> None:
    """The sources of one result, one page at a time with Previous / Next (all_pages: also pages without quotes)."""
    detail = detail or views.question_detail(db, run_id, question_id)
    docs = [d for d in detail["documents"] if all_pages or d["passages"]]
    if not docs:
        st.caption("No quotes were found.")
        return
    pos_key = f"src_{key}"
    pos = min(st.session_state.get(pos_key, 0), len(docs) - 1)
    nav = st.columns([1, 3, 1], vertical_alignment="center")
    if nav[0].button("◀ Previous source", key=f"{pos_key}_prev", disabled=pos == 0, width="stretch"):
        st.session_state[pos_key] = pos - 1
        st.rerun(scope="fragment")
    nav[1].markdown(f"<div style='text-align:center'>Source <b>{pos + 1}</b> of {len(docs)}</div>",
                    unsafe_allow_html=True)
    if nav[2].button("Next source ▶", key=f"{pos_key}_next", disabled=pos >= len(docs) - 1, width="stretch"):
        st.session_state[pos_key] = pos + 1
        st.rerun(scope="fragment")
    d = docs[pos]
    badge = TIER_LABEL.get(d["effective_tier"] or d["registry_tier"], "?")
    purpose = "for the question" if d["mode"] == "A" else "for the note"
    st.markdown(f"#### {d['title'] or d['url']}")
    link = d["url"] if d["url"].startswith("http") else None
    st.markdown(f"{badge}{' · **frame authority**' if d['frame_authority'] else ''} · {purpose} · "
                f"{d['grounded']} quote(s) · read {d['fetched']} · {d['page_kind'] or '-'} · "
                f"{STATUS_TEXT.get(d['status'], d['status'])}"
                + (f" · {d['dropped']} quote(s) rejected (not found word for word)" if d["dropped"] else "")
                + (f"  \n[{d['url']}]({link})" if link else f"  \n`{d['url']}`"))
    if d["concerns"]:
        st.warning("Concerns: " + "; ".join(d["concerns"]))
    if d["about_right_subject"] is False:
        st.error("This page is about a different subject; its quotes are not used.")
    for p in d["passages"]:
        st.markdown(f"<div class='qv-quote'>{html.escape(p['quote'])}</div>", unsafe_allow_html=True)
        meta = [f"about {p['target']}"]
        if p["asserted_answer"]:
            meta.append(f"says the answer is **{p['asserted_answer']}**"
                        + (f" (option {p['matches_option']})" if p["matches_option"] else ""))
        for k, label in (("qualifiers", "only if"), ("as_of", "as of"), ("origin", "credits")):
            if p[k]:
                meta.append(f"{label}: {p[k]}")
        st.caption(f"{p['short_id']}" + (f" · origin {p['cluster']}" if p["cluster"] else "")
                   + " · " + " · ".join(meta))
    if d["passages"] and st.toggle("Show the quotes in their page", key=f"{pos_key}_ctx_{d['doc_id']}{d['mode']}"):
        st.markdown(f"<div class='qv-page'>{highlight(d['text'], d['passages'])}</div>", unsafe_allow_html=True)


def popup_nav(pos_key: str, n: int, what: str, on_move: Callable[[], None] | None = None) -> int:
    """◀ Previous · i of n · Next ▶ for a popup that steps through a list; returns the position."""
    pos = max(0, min(st.session_state.get(pos_key, 0), n - 1))
    if n <= 1:
        return pos
    nav = st.columns([1, 3, 1], vertical_alignment="center")
    for col, step, label, off in ((nav[0], -1, f"◀ Previous {what}", pos == 0),
                                  (nav[2], 1, f"Next {what} ▶", pos >= n - 1)):
        if col.button(label, key=f"{pos_key}_{step}", disabled=off, width="stretch"):
            st.session_state[pos_key] = pos + step
            if on_move:
                on_move()
            st.rerun(scope="fragment")
    nav[1].markdown(f"<div style='text-align:center;opacity:.75'>{what.capitalize()} {pos + 1} of {n}</div>",
                    unsafe_allow_html=True)
    return pos


# --- header bar: the file being worked on --------------------------------------------------

def file_header() -> None:
    """The file being worked on, in the app's top bar: picker, ⓘ details, a running batch, evaluation sets."""
    names = workflow.dataset_names(db, include_eval=st.session_state.get("show_eval", False))
    with st.container(key="qv_header", horizontal=True, vertical_alignment="center", gap="small"):
        if not names:
            st.caption("No file yet — start with Import")
            return
        batch = worker.status(settings.data_dir)
        if batch.running:
            st.markdown("⏳", help=f"Checking {batch.dataset} since {batch.started}")
        if st.session_state.get("_file_pick") != st.session_state.get("dataset"):
            st.session_state["_file_pick"] = st.session_state.get("dataset")

        def picked() -> None:
            st.session_state.dataset = st.session_state["_file_pick"]

        st.selectbox("Working on", names, key="_file_pick", on_change=picked, label_visibility="collapsed",
                     icon=":material/description:", width=220)
        card = {c["file"]: c for c in views.dataset_cards(db, include_eval=True)}.get(st.session_state.dataset)
        with st.popover("", icon=":material/info:", help="About this file", type="tertiary"):
            if card:
                st.markdown(f"**{card['file']}**  \nSource file: {card['source file']}  \nVersion {card['version']} "
                            f"· imported {card['imported']}  \n{card['questions']} questions · profile "
                            f"*{card['profile']}*")
            if batch.running:
                st.markdown(f"⏳ Checking **{batch.dataset}** since {batch.started}")
            st.caption("Switch files here or by clicking a row on the Overview.")
        st.toggle("Eval sets", key="show_eval", help="Also list the evaluation files (eval-…) used to measure how "
                                                     "well the validator works")


# ===========================================================================================
def page_overview() -> None:
    """Every file with its progress, and the next step for the current one."""
    page_title("Overview", "overview")
    cards = views.dataset_cards(db, include_eval=st.session_state.get("show_eval", False))
    if not cards:
        st.info("Nothing imported yet. Import a question file (one per game edition) to begin.")
        if st.button("Go to Import", type="primary"):
            st.switch_page(PAGES["import"])
        return
    st.caption("Your question files — one per game edition. Click a row to work on that file.")
    here = next((i for i, c in enumerate(cards) if c["file"] == st.session_state.get("dataset")), None)

    def switch(row: int, _order: list[int]) -> None:
        if cards[row]["file"] != st.session_state.get("dataset"):
            st.session_state.pending_dataset = cards[row]["file"]
            st.rerun()

    data_table(cards, key="overview_files", highlight=here, on_open=switch,
               columns={"file": TEXT("File"), "source file": TEXT("Source file")})
    name = current()
    st.subheader(f"Working on: {name}")
    c = progress(workflow.question_states(db, name))
    cols = st.columns(4)
    cols[0].metric("✅ Ready", ready(c), help=READY_HELP)
    cols[1].metric("🔍 To look at", sum(c[k] for k in workflow.REVIEW_STATUSES))
    cols[2].metric("⏳ Still to check", c["not_checked"] + c["failed"] + c["in_progress"])
    cols[3].metric("🛑 Format errors", c["format_error"])
    st.caption(f"Ready = 🤖 {c['verified']} verified automatically · 👍 {c['approved']} confirmed by you · "
               f"✏️ {c['edited']} edited by you")
    next_step(name)


# ===========================================================================================
def page_import() -> None:
    """1. new file or update, 2. upload, 3. format check (with fixes), import."""
    from qv.services import datasets as ds_service
    from qv.services.import_fixes import suggest_fixes
    from qv.services.import_help import hint
    page_title("Import a question file", "import")
    existing = workflow.dataset_names(db, include_eval=True)
    dataset = st.session_state.get("dataset")

    st.markdown("#### 1 · What are you importing?")
    target = st.radio("Import as", ["An update of a file I already imported", "A new file (e.g. another edition)"],
                      index=0 if existing else 1, disabled=not existing, label_visibility="collapsed")
    if target.startswith("An update") and existing:
        c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
        name = c1.selectbox("Which file", existing, index=existing.index(dataset) if dataset in existing else 0)
        profile = workflow.dataset_profile(db, name) or "general"
        c2.caption(f"Profile *{profile}*. Questions with the same id and text keep their results and decisions; "
                   "new and changed questions are checked.")
    else:
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", placeholder="e.g. world-tour", help="Short name, used in commands")
        profiles = available_profiles()
        profile = c2.selectbox("Edition profile", profiles,
                               index=profiles.index("general") if "general" in profiles else 0,
                               help="Decides the audience and, for Swab Quest and Prophets' Stories, the "
                                    "Ahmadiyya understanding")

    st.markdown("#### 2 · Choose the file")
    up = st.file_uploader("Question file (.csv)", type=["csv"], disabled=not name,
                          help="The game's CSV format: id, question, type, answer (required), opt_a–opt_d, "
                               "difficulty, category, subcategory, topic, note — details under Help"
                          if name else "Give the new file a name first")
    if up is None or not name:
        return

    st.markdown("#### 3 · Check and import")
    fixed_key = f"fixed_{up.file_id}_{profile}"
    data = st.session_state.get(fixed_key) or up.getvalue()
    if fixed_key in st.session_state:
        st.success("✨ Fixes applied. The file below is the fixed one — download it to update your own copy "
                   "(importing does not change the file on your computer).")
        st.download_button("⬇ Download the fixed file", data, file_name=up.name, mime="text/csv")
    else:
        fx = suggest_fixes(data, load_profile(profile))
        if fx.fixes:
            with st.container(border=True):
                st.markdown(f"**✨ {len(fx.fixes)} problem(s) can be fixed for you** — only changes whose result "
                            "is certain; ids never change. Look at the list, then press the button.")
                with st.expander("What will change"):
                    data_table([{"line": f.line_no, "id": f.ext_id, "change": f.what} for f in fx.fixes],
                               key="fix_list", columns={"change": TEXT("Change", width="large")})
                if st.button("Fix them for me", type="primary"):
                    st.session_state[fixed_key] = fx.data
                    st.rerun()
    result = ds_service.check_bytes(data, load_profile(profile))
    rep = result.report
    errors = [i for i in rep.issues if i.severity == "error"]
    warnings = [i for i in rep.issues if i.severity == "warning"]
    st.markdown(f"**Format check: {len(result.questions)} questions**")
    if not rep.issues:
        st.success("No format problems.")
    else:
        (st.error if errors else st.warning)(
            f"{len(errors)} error(s) and {len(warnings)} warning(s). Errors must be fixed before those "
            "questions can be checked; warnings are fine to import.")
        groups: dict[tuple[str, str], list] = {}
        for i in rep.issues:
            groups.setdefault((i.code, i.severity), []).append(i)
        column_titles = {"missing_column": "Missing columns", "unknown_column": "Columns the game does not use",
                         "duplicate_column": "Duplicate columns"}
        for n, ((code, sev), items) in enumerate(sorted(groups.items(),
                                                        key=lambda kv: ["error", "warning", "info"].index(kv[0][1]))):
            icon = "🛑" if sev == "error" else "⚠️" if sev == "warning" else "ℹ️"
            if code in column_titles:
                title = ("Missing required column" if sev == "error" and code == "missing_column"
                         else column_titles[code]) + ": " + ", ".join(i.column or "?" for i in items)
            else:
                lines = ", ".join(str(i.line_no) for i in items[:12] if i.line_no)
                title = code.replace("_", " ").capitalize() + (f" — {len(items)}×" if len(items) > 1 else "") + (
                    f" (line{'s' if len(items) > 1 else ''} {lines}{' …' if len(items) > 12 else ''})" if lines else "")
            with st.expander(f"{icon} {title}"):
                per_item = code in column_titles
                if not per_item:
                    st.markdown(f"**What to do:** {hint(items[0], result.parsed.header)}")
                data_table([{"line": i.line_no, "id": i.ext_id, "column": i.column, "problem": i.message,
                             **({"what to do": hint(i, result.parsed.header)} if per_item else {})} for i in items],
                           key=f"issues_{n}", columns={"problem": TEXT("Problem", width="large"),
                                                       "what to do": TEXT("What to do", width="large")})
    if any(i.code == "missing_column" for i in errors):
        st.error("A required column is missing, so the file cannot be imported. Fix the header line and upload it "
                 "again.")
        return
    if st.button(f"Import into '{name}'", type="primary"):
        with db.session() as s:
            res = ds_service.import_dataset(s, data, dataset_name=name, source_filename=up.name, profile_name=profile)
        if not res.created:
            st.info(f"This file is identical to version {res.version_no} — nothing new to import.")
        else:
            msg = f"Imported as version {res.version_no} of **{name}**."
            if res.diff is not None:
                d = res.diff
                msg += (f" Since the previous version: {len(d.added)} added, {len(d.changed)} changed, "
                        f"{len(d.removed)} removed — only new and changed questions need checking.")
            st.success(msg)
        st.session_state.imported = name
    if st.session_state.get("imported") == name and st.button("Next: Validate", type="primary"):
        st.session_state.pending_dataset = name
        st.switch_page(PAGES["validate"])


# ===========================================================================================
def page_validate() -> None:
    """Choose the next batch (which questions, order, size), start it; follow a running batch."""
    name = current()
    page_title("Validate", "validate")
    states = workflow.question_states(db, name)
    c = progress(states)

    @st.fragment(run_every=5)
    def live() -> None:
        """Status of the running batch (refreshes every few seconds)."""
        b = worker.status(settings.data_dir)
        log = b.log if b.running else worker.latest_log(settings.data_dir, name)
        if b.running:
            st.info(f"⏳ Checking **{b.dataset}** — started {b.started}. You can close this page.")
        text = worker.tail(log, 12)
        if text:
            with st.expander("Batch log" + (" (running)" if b.running else " (last batch)"), expanded=b.running):
                st.code(text, language=None)
        if not b.running and st.session_state.get("was_running"):
            st.session_state.was_running = False
            st.rerun()
        st.session_state.was_running = b.running

    live()
    running = worker.status(settings.data_dir).running
    left = [s for s in states if s.status in workflow.CHECKABLE]

    with st.container(border=True):
        st.markdown("#### Choose the next batch")
        st.markdown("**1 · Which questions**")
        which = st.segmented_control(
            "Which questions", ["all", "some", "ids"], default="all", key=f"which_{name}",
            format_func={"all": f"All still to check ({len(left)})", "some": "Only some (by category, difficulty …)",
                         "ids": "Only these ids"}.get, label_visibility="collapsed") or "all"
        sel_cats = sel_subs = sel_topics = sel_diffs = sel_levels = []
        ids: list[str] = []
        if which == "some":
            f = st.columns(5)
            cats = sorted({s.category for s in left if s.category})
            sel_cats = f[0].multiselect("Category", cats, placeholder="any")
            subs = sorted({s.subcategory for s in left if s.subcategory and (not sel_cats or s.category in sel_cats)})
            sel_subs = f[1].multiselect("Subcategory", subs, placeholder="any")
            topics = sorted({s.topic for s in left if s.topic and (not sel_cats or s.category in sel_cats)
                             and (not sel_subs or s.subcategory in sel_subs)})
            sel_topics = f[2].multiselect("Topic", topics, placeholder="any")
            sel_diffs = f[3].multiselect("Difficulty", sorted({s.difficulty for s in left if s.difficulty}),
                                         placeholder="any")
            sel_levels = f[4].multiselect("Fact-heavy wording", ["high", "medium", "low"], placeholder="any",
                                          help="Wording where quiz answers most often go wrong (numbers, "
                                               "'first / only', dates …) — not a prediction. Details under Help")
        elif which == "ids":
            text = st.text_input("Ids", placeholder="e.g. 1, 5, 10-12", label_visibility="collapsed")
            ids = workflow.parse_ids(text) or []

        st.markdown("**2 · In which order**")
        order = st.radio("Order", list(workflow.ORDERS), format_func=workflow.ORDERS.get, horizontal=True,
                         key=f"order_{name}", label_visibility="collapsed",
                         help="Questions you edited always come first. 'Fact-heavy wording' only changes the order "
                              "— explained under Help.")

        st.markdown("**3 · How many**")
        default = load_research_config().batch_size
        today = workflow.suggested_batch_size(db, default)
        g = st.columns([1, 3], vertical_alignment="center")
        size = g[0].number_input("Questions in this batch", min_value=1, max_value=200, value=today or default,
                                 label_visibility="collapsed")
        reset = workflow.next_reset_local()
        g[1].caption(f"Today's free AI requests allow about **{today}** question(s) (at most {default} per batch). "
                     f"A batch stops by itself when a free limit is reached; the limits come back at "
                     f"{reset:%H:%M}.")
        sel = workflow.Selection(categories=tuple(sel_cats), subcategories=tuple(sel_subs), topics=tuple(sel_topics),
                                 difficulties=tuple(sel_diffs), levels=tuple(sel_levels), ids=tuple(ids), order=order)
        plan = workflow.plan_next_batch(db, name, sel, int(size))
        if plan.action == "resume":
            st.info("A batch stopped before it was finished (usually a free limit). It is continued first; your "
                    "choice above is used for the batch after it.")
        st.markdown(f"**{plan.message}**")
        if plan.questions:
            data_table([{"id": q.ext_id, "difficulty": q.difficulty, "question": q.question,
                         "category": path(q.category, q.subcategory, q.topic),
                         **({"why first": ", ".join(q.priority_reasons)} if order == "risk" else {})}
                        for q in plan.questions], key=f"plan_{name}", columns=COLS_QUESTION, max_rows=8)
        label = "▶ Continue the stopped batch now" if plan.action == "resume" else "▶ Start checking now"
        if running:
            st.button(label, disabled=True, help="A batch is already running")
        elif today == 0 and plan.action != "nothing":
            st.warning(f"Today's free AI requests are used up. They come back at **{reset:%H:%M} ({reset:%A})**.")
            st.button(label, disabled=True, help="Today's free AI requests are used up")
        elif plan.action != "nothing" and st.button(label, type="primary"):
            args = ["--size", str(int(size)), "--order", sel.order]
            for flag, values in (("--category", sel.categories), ("--subcategory", sel.subcategories),
                                 ("--topic", sel.topics), ("--difficulty", sel.difficulties), ("--risk", sel.levels)):
                for v in values:
                    args += [flag, v]
            if sel.ids:
                args += ["--ids", ",".join(sel.ids)]
            worker.start_background(settings.data_dir, name, args)
            st.rerun()
        st.caption("The batch starts right away and runs in the background — you can close this page. "
                   f"Terminal: `qv next {name}` does the same.")
    st.page_link(PAGES["daily"], label="Let your Mac do this every day by itself → Daily run", icon="⏰")
    if c["format_error"]:
        st.warning(f"{c['format_error']} question(s) have format errors and are skipped — fix them in the file "
                   "and import it again.")



# ===========================================================================================
def page_daily() -> None:
    """Turn the automatic daily batch on or off."""
    from datetime import time as _time

    from qv.services import daily
    page_title("⏰ Daily run", "daily", "Your Mac starts a batch every day by itself: all questions still to check, "
                                         "in file order, for the files you choose.")
    stat = daily.status(settings.data_dir)
    (st.success if stat.on else st.info)(
        f"**On** — every day at {stat.settings.time_text} for {', '.join(stat.settings.datasets)}" if stat.on
        else "**Off** — batches only run when you press *Start checking now* on the Validate page.")
    with st.container(border=True):
        names = workflow.dataset_names(db)
        here = st.session_state.get("dataset")
        chosen = [d for d in stat.settings.datasets if d in names] or [n for n in [here] if n in names]
        files = st.multiselect("Files, in this order", names, default=chosen, key="daily_files")
        reset = workflow.next_reset_local()
        default = stat.settings if stat.on else daily.DailySettings(
            hour=((reset.hour * 60 + reset.minute + 15) // 60) % 24, minute=(reset.minute + 15) % 60)
        at = st.time_input("Time", value=_time(default.hour, default.minute), step=900,
                           help=f"The free limits reset at {reset:%H:%M} your time; a little after that is best.")
        b1, b2, _ = st.columns([2, 2, 4])
        if b1.button("Save and turn on" if not stat.on else "Save changes", type="primary", disabled=not files,
                     width="stretch"):
            try:
                daily.turn_on(settings.data_dir, daily.DailySettings(list(files), at.hour, at.minute))
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
            else:
                st.rerun()
        if stat.on and b2.button("Turn off", width="stretch"):
            daily.turn_off()
            st.rerun()
    text = worker.tail(stat.log, 12)
    if text:
        st.markdown("**Last daily run**")
        st.code(text, language=None)



# ===========================================================================================
def page_review() -> None:
    """Every checked question in a table; click one to open it in a popup and decide."""
    name = current()
    page_title("Review", "review")
    states = workflow.question_states(db, name)
    edits = workflow.pending_edits(states)
    if edits:
        st.info(f"✏️ You edited {len(edits)} question(s). Export them as they are, or check them again with the "
                "new wording first (they then go to the front of the next batch).")
        if st.button("Check my edits again"):
            v = workflow.apply_edits_as_new_version(db, name)
            st.toast(f"Saved as version {v}. Validate the next batch to check the edited questions.")
            st.rerun()
    groups = {k: [s for s in states if s.status in sts] for k, sts in workflow.REVIEW_GROUPS.items()}
    if not groups["all"]:
        st.info("Nothing has been checked yet.")
        next_step(name)
        return
    default = next((k for k in ("to_review", "specialist", "no_evidence", "spot_check") if groups[k]), "all")
    group = st.segmented_control("Show", list(groups), format_func=lambda k: f"{GROUP_LABEL[k]} ({len(groups[k])})",
                                 default=default, key=f"group_{name}") or default
    st.caption(GROUP_HELP[group])
    bar = st.columns([3, 2], vertical_alignment="bottom")
    cats = sorted({s.category for s in groups[group] if s.category})
    sel_cats = bar[0].multiselect("Category", cats, placeholder="All categories", label_visibility="collapsed")
    items = [s for s in groups[group] if not sel_cats or s.category in sel_cats]
    items.sort(key=lambda s: (s.later, s.row_no))
    if group == "specialist" and items:
        from qv.services.exports import results_csv
        bar[1].download_button("⬇ List for your specialist (CSV)", results_csv(db, items),
                               file_name=f"{name}-for-specialist.csv", mime="text/csv")

    def open_question(row: int, order: list[int]) -> None:
        st.session_state["rv_ids"] = [items[i].ext_id for i in order]
        st.session_state["rv_pos"] = order.index(row) if row in order else 0
        st.session_state["rv_view_next"] = "result"
        review_dialog(name)

    data_table([{"status": status_text(s) + (" · later" if s.later else ""), "id": s.ext_id,
                 "question": s.question, "answer": s.answer_text, "result": s.verdict,
                 "your decision": s.decision, "category": path(s.category, s.subcategory, s.topic)}
                for s in items], key=f"review_{name}_{group}_{','.join(sel_cats)}", columns=COLS_QUESTION,
               search="🔎 Search: words in the question or answer, or an id", on_open=open_question)


@st.dialog("Review a question", width="large", on_dismiss="rerun")
def review_dialog(name: str) -> None:
    """One question: result, sources (one at a time) and the decision; Previous / Next through the list."""
    ids: list[str] = st.session_state.get("rv_ids") or []
    if not ids:
        return
    if "rv_view_next" in st.session_state:          # a move to another question shows its result first
        st.session_state["rv_view"] = st.session_state.pop("rv_view_next")
    pos = popup_nav("rv_pos", len(ids), "question", on_move=lambda: st.session_state.update(rv_view_next="result"))
    item = {s.ext_id: s for s in workflow.question_states(db, name)}.get(ids[pos])
    if item is None:
        st.warning("This question is no longer in the file.")
        return
    st.markdown(f"#### #{item.ext_id} · {status_text(item)}")
    st.markdown(f"**{item.question}**")
    if item.type == "multi":
        key_idx = int(item.answer) - 1 if item.answer.isdigit() else -1
        st.markdown("  ·  ".join(("✅ " if i == key_idx else "") + f"**{'ABCD'[i]}.** {o}"
                                 for i, o in enumerate(item.options) if o))
    else:
        st.markdown(f"**Answer:** {item.answer_text}")
    if item.note:
        st.markdown(f"**Note:** {item.note}")
    st.caption(f"{path(item.category, item.subcategory, item.topic)} · {item.difficulty}")
    v = views.question_verdict(db, item.run_id, item.ext_id) if item.run_id else None
    detail = views.question_detail(db, item.run_id, v["question_id"]) if v else None
    n_src = sum(1 for d in detail["documents"] if d["passages"]) if detail else 0
    if st.session_state.get("rv_view") not in ("result", "sources"):
        st.session_state["rv_view"] = "result"
    view = st.segmented_control("View", ["result", "sources"], key="rv_view",
                                format_func={"result": "📋 Result", "sources": f"📄 Sources ({n_src})"}.get,
                                label_visibility="collapsed") or "result"
    with st.container(border=True):
        if view == "result":
            if v:
                verdict_box(v)
                st.markdown("**Why**\n" + "\n".join(f"- {r}" for r in v["reasons_json"]))
                issues = (v["quality_json"] or {}).get("issues", [])
                if issues:
                    st.markdown("**Quality notes**\n" + "\n".join(
                        f"- {i['type'].replace('_', ' ')} ({i['severity']}): {i['detail']}" for i in issues))
            else:
                st.caption("No result for this question yet.")
        elif v:
            source_viewer(item.run_id, v["question_id"], f"rv_{item.ext_id}", detail=detail)
        else:
            st.caption("No sources yet.")
    decision_panel(name, item, v, last=pos >= len(ids) - 1)


def decision_panel(name: str, item: workflow.QuestionState, v: dict | None, *, last: bool) -> None:
    """The decision buttons (inside the review popup). After a decision the popup moves to the next question."""
    st.markdown("**Your decision**")
    hist = workflow.decision_history(db, name, item.ext_id)
    if hist:
        st.caption("So far: " + " · ".join(f"{h['when']} **{h['action']}**"
                                                         + (f" ({h['comment']})" if h["comment"] else "")
                                                         for h in hist))
    comment = st.text_input("Comment (optional)", key=f"comment_{item.ext_id}", placeholder="Comment (optional)",
                            label_visibility="collapsed")
    b = st.columns(5)

    def decide(action: str, changes: dict | None = None) -> None:
        workflow.record_decision(db, name, item.ext_id, action, changes=changes, comment=comment)
        st.toast(f"#{item.ext_id}: {action}" + ("" if last else " — next question"))
        if not last:
            st.session_state["rv_pos"] = st.session_state.get("rv_pos", 0) + 1
            st.session_state["rv_view_next"] = "result"
        st.rerun(scope="fragment")

    if b[0].button("👍 Confirm", help="It is right as it is: you checked it", width="stretch", type="primary"):
        decide("keep")
    if b[1].button("✎ Edit", help="Change the question, options, answer or note", width="stretch"):
        st.session_state[f"editing_{item.ext_id}"] = True
    if b[2].button("🎓 Specialist", help="Ask the specialist: puts it on the list for your reviewer", width="stretch"):
        decide("specialist")
    if b[3].button("✖ Remove", help="Leave it out of the exported file", width="stretch"):
        decide("remove")
    if b[4].button("⏭ Later", help="Moves it to the end of the list", width="stretch"):
        decide("later")
    st.caption("After a decision the next question opens. Close the popup to see the updated list.")
    if st.session_state.get(f"editing_{item.ext_id}"):
        edit_form(name, item, v, last=last)


def edit_form(name: str, item: workflow.QuestionState, v: dict | None, *, last: bool) -> None:
    """Change question, options, answer or note (optionally starting from the suggestion)."""
    sugg_q = (v or {}).get("suggested_question") or ""
    sugg_a = (v or {}).get("suggested_answer") or ""
    use = st.checkbox("Start from the suggestion", value=bool(sugg_q or sugg_a), disabled=not (sugg_q or sugg_a),
                      key=f"use_sugg_{item.ext_id}")
    with st.form(f"edit_{item.ext_id}"):
        new = {"question": st.text_input("Question", sugg_q if use and sugg_q else item.question)}
        if item.type == "multi":
            opts = st.columns(4)
            for i, col in enumerate(("opt_a", "opt_b", "opt_c", "opt_d")):
                new[col] = opts[i].text_input(f"Option {'ABCD'[i]} ({i + 1})", item.options[i])
            guess = item.answer
            if use and sugg_a:
                for i, o in enumerate(item.options):
                    if o and o.casefold() in sugg_a.casefold():
                        guess = str(i + 1)
            new["answer"] = st.selectbox("Right option", ["1", "2", "3", "4"],
                                         index=["1", "2", "3", "4"].index(guess) if guess in "1234" else 0)
            if use and sugg_a:
                st.caption(f"Suggested answer: {sugg_a}")
        else:
            new["answer"] = st.text_input("Answer", sugg_a if use and sugg_a else item.answer)
        new["note"] = st.text_area("Note", item.note)
        if st.form_submit_button("Save the edit", type="primary"):
            try:
                workflow.record_decision(db, name, item.ext_id, "edit", changes=new,
                                         comment=st.session_state.get(f"comment_{item.ext_id}", ""))
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state[f"editing_{item.ext_id}"] = False
                st.toast(f"#{item.ext_id}: edited")
                if not last:
                    st.session_state["rv_pos"] = st.session_state.get("rv_pos", 0) + 1
                    st.session_state["rv_view_next"] = "result"
                st.rerun(scope="fragment")


# ===========================================================================================
def page_export() -> None:
    """The three downloads and what to do with them."""
    from qv.services.exports import ExportError, workflow_export
    name = current()
    page_title("Export", "export")
    states = workflow.question_states(db, name)
    c = workflow.counts(states)
    open_ = sum(c[k] for k in workflow.REVIEW_STATUSES) + c["not_checked"] + c["failed"]
    m = st.columns(4)
    m[0].metric("Questions", len(states))
    m[1].metric("✅ Ready", ready(c), help=READY_HELP)
    m[2].metric("✖️ Removed", c["removed"])
    m[3].metric("Still open", open_, help="To review, for a specialist, not enough evidence, spot check, or not "
                                          "checked yet")
    st.caption(f"Ready = 🤖 {c['verified']} verified automatically · 👍 {c['approved']} confirmed by you · "
               f"✏️ {c['edited']} edited by you")
    if open_:
        st.info("You can export at any time: open questions stay unchanged in the corrected file and are left out "
                "of the ready-only file.")
    downloads = [
        ("corrected", "⬇ Corrected file", "The whole file with your edits applied and removed questions left out. "
                                         "Same ids, same order, format checked again. **This one goes into the "
                                         "game.**"),
        ("ready", "⬇ Ready questions only", f"Only the {ready(c)} questions ready for the game: 🤖 verified "
                                            f"automatically ({c['verified']}), 👍 confirmed by you "
                                            f"({c['approved']}) and ✏️ edited by you ({c['edited']})."),
        ("results", "⬇ Results report", "One line per question: result, your decision, suggestions, reasons and "
                                       "sources (opens in Excel / Numbers)."),
    ]
    for kind, label, text in downloads:
        with st.container(border=True):
            cols = st.columns([2, 5])
            try:
                data, fname, summary = workflow_export(db, name, kind)
                cols[0].download_button(label, data, file_name=fname, mime="text/csv", width="stretch",
                                        type="primary" if kind == "corrected" else "secondary")
                cols[1].markdown(text + "  \n" + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in summary.items()))
            except ExportError as exc:
                cols[0].button(label, disabled=True, key=f"x_{kind}")
                cols[1].error(f"Cannot build this file: {exc}")
    st.caption("Then copy the corrected file to `game_editions/<edition>/questions.csv` and run "
               "`npm run build:content` — see Help.")


# ===========================================================================================
# Advanced
def page_batches() -> None:
    """Batches and their questions; a question opens with every source in a popup."""
    page_title("Batches", "batches", "Every batch that was run, and everything about each checked question.")
    dataset = st.session_state.get("dataset")
    runs = views.runs_overview(db)
    mine = st.toggle(f"Only batches of {dataset}", value=True) if dataset else False
    runs = [r for r in runs if not mine or r["dataset"] == dataset]
    st.markdown("**Batches** — click one to see its questions")
    r_pick = data_table([{"batch": r["run"], "file": r["dataset"], "version": r["version"], "started": r["created"],
                          "status": r["status"], "done": r["done"], "failed": r["failed"],
                          "left": r["pending"] + r["stopped"], "stopped because": r["stop_reason"]} for r in runs],
                        key=f"adv_runs_{mine}", select=True, max_rows=6,
                        columns={"stopped because": TEXT("Stopped because", width="large")})
    if r_pick is None:
        return
    run_id = runs[r_pick]["run"]
    qs = views.run_questions(db, run_id)
    st.markdown(f"**Questions in batch {run_id}** — click one to see everything about it")

    def open_q(row: int, order: list[int]) -> None:
        st.session_state["bq_list"] = [(run_id, qs[i]["_qid"]) for i in order]
        st.session_state["bq_pos"] = order.index(row) if row in order else 0
        batch_question_dialog()

    data_table(qs, key=f"adv_q_{run_id}", columns=COLS_QUESTION, on_open=open_q)


@st.dialog("Checked question", width="large", on_dismiss="rerun")
def batch_question_dialog() -> None:
    """Everything about one checked question (Previous / Next through the batch)."""
    items = st.session_state.get("bq_list") or []
    if not items:
        return
    pos = popup_nav("bq_pos", len(items), "question")
    run_id, question_id = items[pos]
    detail = views.question_detail(db, run_id, question_id)
    q = detail["question"]
    st.markdown(f"#### #{q['id']} {q['question']}")
    if q["type"] == "multi":
        st.markdown("  ·  ".join(f"**{'ABCD'[i]}.** {o}" for i, o in enumerate(q["options"]) if o))
    st.markdown(f"**Expected answer:** {q['key']}" + (f"  ·  **Note:** {q['note']}" if q["note"] else ""))
    tab_r, tab_s, tab_p = st.tabs(["📋 Result", "📄 Every page that was read", "🔧 Research plan & numbers"])
    with tab_r:
        v = views.question_verdict(db, run_id, q["id"])
        if v is None:
            st.info(f"Not judged in this batch (`qv judge {run_id}` gives a verdict).")
        else:
            verdict_box(v)
            st.markdown("**Why**\n" + "\n".join(f"- {r}" for r in v["reasons_json"]))
    with tab_s:
        source_viewer(run_id, question_id, f"bq_{run_id}_{question_id}", all_pages=True, detail=detail)
    with tab_p:
        st.json({k: s["output"] for k, s in detail["stages"].items() if k in ("s1a", "s1b")}, expanded=False)
        st.json(detail["stats"], expanded=False)


def page_files() -> None:
    """Imported files and versions; a version's questions and format problems."""
    page_title("Files & versions", "files", "Every imported file and version. Imports are never changed; "
                                           "corrections exist only in exports.")
    overview = views.datasets_overview(db)
    st.markdown("**Imported files and versions** — click one to see its questions and format problems")
    v_pick = data_table(overview, key="adv_versions", select=True, max_rows=8, columns={"version_id": None})
    if v_pick is None:
        return
    vid = overview[v_pick]["version_id"]
    t1, t2 = st.tabs(["Questions", "Format problems"])
    with t1:
        data_table(views.version_questions(db, vid), key=f"adv_vq_{vid}", search=True,
                   columns={**COLS_QUESTION, "_qid": None})
    with t2:
        issues = views.version_issues(db, vid)
        sev = st.pills("Severity", ["error", "warning", "info"], selection_mode="multi", default=["error", "warning"])
        data_table([i for i in issues if i["severity"] in sev], key=f"adv_vi_{vid}",
                   columns={"message": TEXT("Message", width="large")})


def page_usage() -> None:
    """Free quota left and calls so far."""
    page_title("Usage & quota", "usage")
    st.markdown("**Free quota left now**")
    data_table(views.quota_rows(db), key="quota", max_rows=15)
    st.caption(f"Gemini's daily limits come back at {workflow.next_reset_local():%H:%M} local time.")
    st.markdown("**Calls so far** (free tiers only: cost is always $0)")
    data_table(views.usage_summary(db), key="usage", max_rows=15)


# --- book library --------------------------------------------------------------------------
def editions() -> list[str]:
    """Game editions a book can be used for (the edition profiles)."""
    return [p for p in available_profiles() if p != "general"]


def book_info_form(key: str, *, title: str = "", source_url: str = "") -> tuple[bool, object]:
    """Title, author, language, publisher, trust, editions → (submitted, BookInfo)."""
    from qv.services.books import BookInfo
    c = st.columns([3, 2])
    t = c[0].text_input("Title", title, key=f"{key}_title")
    author = c[1].text_input("Author", key=f"{key}_author")
    c = st.columns(3)
    lang = c[0].text_input("Language (en, de, ur …)", "en", key=f"{key}_lang")
    publisher = c[1].text_input("Publisher's website", "alislam.org", key=f"{key}_pub",
                                help="An official source of the edition's tradition when it is one of the frame's "
                                     "authorities (e.g. alislam.org)")
    tier = c[2].selectbox("Trust", ["P", "S", "T"], index=1, format_func=TIER_LABEL.get, key=f"{key}_tier")
    eds = st.multiselect("Used for these editions", editions(), default=[e for e in ("swab-quest", "prophets-stories")
                                                                        if e in editions()], key=f"{key}_eds")
    url = st.text_input("Where it comes from (optional)", source_url, key=f"{key}_url")
    tr = st.checkbox("Not in English: also translate it for searching (uses free Flash-Lite requests, one per page; "
                     "`qv library translate`)", key=f"{key}_tr")
    info = BookInfo(title=t, author=author, language=lang, publisher=publisher, tier=tier, editions=tuple(eds),
                    source_url=url, translate_for_search="en" if tr else None)
    return bool(t.strip()), info


def report_index(rep) -> None:  # noqa: ANN001
    """What reading the books did, in plain words."""
    if rep.needs_ocr:
        st.warning("No usable text in: " + ", ".join(rep.needs_ocr) + " — the PDF's letters cannot be read (it needs "
                   "OCR, not built yet). It is kept but not searched.")
    if rep.indexed:
        st.success("Read: " + ", ".join(f"{b} ({n} pages)" for b, n in rep.indexed.items()))


@st.dialog("Add a book", width="large", on_dismiss="rerun")
def add_book_dialog() -> None:
    """Upload a PDF and describe it."""
    from qv.services.books import add_book, guess_title
    up = st.file_uploader("The book (PDF)", type=["pdf"], key="book_upload")
    ok, info = book_info_form("addbook", title=guess_title(up.name) if up else "")
    if st.button("Add and read the book", type="primary", disabled=up is None or not ok):
        with st.spinner("Reading the book …"):
            try:
                book, rep = add_book(settings.data_dir, up.getvalue(), info)
            except ValueError as exc:
                st.error(str(exc))
                return
        report_index(rep)
        st.success(f"Added **{book.title}** — it is used from the next batch on.")


@st.dialog("Book", width="large", on_dismiss="rerun")
def book_dialog(book_id: str) -> None:
    """One book: what it is, its state, remove it."""
    from qv.library import Library
    from qv.services.books import remove_book
    lib = Library(settings.data_dir)
    b = lib.books.get(book_id)
    if b is None:
        st.info("This book was removed.")
        return
    row = next((r for r in lib.status() if r["book"] == book_id), {})
    st.markdown(f"#### {b.title}" + (f" — {b.author}" if b.author else ""))
    st.markdown(f"Language **{b.language}** · trust **{TIER_LABEL[b.tier]}** · publisher **{b.publisher or '—'}** · "
                f"used for **{', '.join(b.editions) or 'no edition'}**  \n"
                f"{row.get('state', '')} · {row.get('pages') or '?'} pages · file `{b.file}`"
                + (f"  \nTranslated for search: {row['translated for search']}" if row.get("translated for search")
                   else "") + (f"  \nFrom: {b.source_url}" if b.source_url else ""))
    st.divider()
    st.markdown("**Remove this book**")
    st.caption("Deletes the PDF from the books folder and its pages from the search index. Quotes already used as "
               "evidence stay in the results (they are history).")
    sure = st.checkbox("Yes, remove it", key=f"rm_{book_id}")
    if st.button("🗑 Remove the book", disabled=not sure, key=f"rmb_{book_id}"):
        remove_book(settings.data_dir, book_id)
        st.success("Removed.")
        st.rerun()


@st.dialog("Book found on the web", width="large", on_dismiss="rerun")
def candidate_dialog(item: dict) -> None:
    """A web PDF: download and add it, or hide it."""
    from qv.services.books import add_book, dismiss, download_pdf, guess_title
    st.markdown(f"#### {item['file']}")
    st.markdown(f"Site **{item['site']}** · seen {item['seen']}  \n[{item['url']}]({item['url']})")
    st.caption("The research met this PDF on the web but does not read web PDFs. If it is a trustworthy book, add "
               "it to the library: it is then searched for every question of the chosen editions.")
    ok, info = book_info_form(f"cand_{hash(item['url'])}", title=guess_title(item["file"]), source_url=item["url"])
    c = st.columns(2)
    if c[0].button("⬇ Download and add", type="primary", disabled=not ok, width="stretch"):
        with st.spinner("Downloading and reading …"):
            try:
                book, rep = add_book(settings.data_dir, download_pdf(item["url"]), info)
            except ValueError as exc:
                st.error(str(exc))
                return
        report_index(rep)
        st.success(f"Added **{book.title}**.")
    if c[1].button("🙈 Not a book for the library", width="stretch"):
        dismiss(settings.data_dir, item["url"])
        st.rerun()


@st.dialog("Search result", width="large", on_dismiss="rerun")
def search_hit_dialog(words: list[str]) -> None:
    """One page that matched, the search words marked; Previous / Next through the results."""
    from qv.library import Library
    hits = st.session_state.get("lib_hits") or []
    if not hits:
        return
    pos = popup_nav("lib_pos", len(hits), "result")
    lib = Library(settings.data_dir)
    hit = lib.page(*hits[pos])
    if hit is None:
        st.info("This page is no longer in the index.")
        return
    st.markdown(f"#### {lib.title_for(hit)}")
    st.caption(f"Cited as `{hit.url}` · the marked words are your search")
    lang = lib.books[hit.book_id].translate_for_search
    tr = lib.translation(hit.book_id, hit.page, lang) if lang else None
    if tr:
        c1, c2 = st.columns(2)
        c1.caption("Original (the evidence)")
        c1.markdown(f"<div class='qv-page'>{mark_words(hit.text, words)}</div>", unsafe_allow_html=True)
        c2.caption("Machine translation (only to find the page)")
        c2.markdown(f"<div class='qv-page'>{mark_words(tr, words)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='qv-page'>{mark_words(hit.text, words)}</div>", unsafe_allow_html=True)


def page_library() -> None:
    """Tabs: search the books (first), the books, books found on the web."""
    from qv.library import Library, query_words
    from qv.services.books import dismissed
    page_title("📚 Book library", "library", "Books used as a source, cited as book + page. They stay on your Mac.")
    lib = Library(settings.data_dir)
    books = lib.status()
    gone = dismissed(settings.data_dir)
    known = {b.source_url for b in lib.books.values()}
    found = [f for f in views.pdfs_found_on_web(db) if f["url"] not in gone and f["url"] not in known]
    t_search, t_books, t_found = st.tabs(["🔎 Search", f"📚 Books ({len(books)})",
                                          f"🌐 Found on the web ({len(found)})"])

    with t_books:
        c = st.columns([2, 2, 6], vertical_alignment="center")
        if c[0].button("➕ Add a book (PDF)", type="primary", width="stretch"):
            add_book_dialog()
        if c[1].button("🔄 Refresh", width="stretch",
                       help="Reads PDFs you put into the books folder yourself and listed in config/library.yaml "
                            "(books added with ➕ are read at once)"):
            with st.spinner("Reading the books …"):
                report_index(lib.index_books())
        data_table(books, key="lib_books", search=False, columns={"title": TEXT("Title", width="large")},
                   on_open=lambda row, _o: book_dialog(books[row]["book"]))

    with t_found:
        st.caption("PDFs the research met but could not read. Click one to download and add it, or to hide it.")
        data_table(found, key="lib_found", max_rows=10,
                   columns={"file": TEXT("File", width="medium"), "url": TEXT("Link", width="large")},
                   on_open=lambda row, _o: candidate_dialog(found[row]))

    with t_search:
        c = st.columns([4, 3])
        query = c[0].text_input("Search", placeholder="🔎 e.g. first Jalsa Salana Qadian",
                                label_visibility="collapsed")
        searchable = [r["book"] for r in books if r["state"] == "searchable"]
        which = c[1].multiselect("Books", searchable, default=searchable, label_visibility="collapsed",
                                 format_func=lambda b: lib.books[b].title, placeholder="Which books")
        if not query:
            st.caption("Type words to find the pages that contain them; click a result to read the page with your "
                       "words marked.")
            return
        words = query_words(query)
        hits = lib.search(query, books=which, limit=20)
        if not hits:
            st.caption("No page matches.")
            return

        def open_hit(row: int, order: list[int]) -> None:
            st.session_state["lib_hits"] = [(hits[i].book_id, hits[i].page) for i in order]
            st.session_state["lib_pos"] = order.index(row) if row in order else 0
            search_hit_dialog(words)

        def where(h) -> str:  # noqa: ANN001
            lang = lib.books[h.book_id].translate_for_search
            tr = lib.translation(h.book_id, h.page, lang) if lang else None
            return (snippet(h.text, words) or (f"(translation) {snippet(tr, words)}" if tr and snippet(tr, words)
                                               else snippet(h.text, words[:1]) or h.text[:90]))

        data_table([{"book": lib.books[h.book_id].title, "page": h.printed or "", "pdf page": h.page,
                     "match": where(h), "score": round(h.score, 1)} for h in hits],
                   key=f"lib_hits_{query}_{','.join(which)}", search=False,
                   columns={"match": TEXT("Where it matches", width="large")}, on_open=open_hit)


# --- websites ------------------------------------------------------------------------------
def page_websites() -> None:
    """Websites research could not read, unlisted sites that gave quotes, and the person's own list."""
    from qv.services import websites as ws
    page_title("🌐 Websites", "websites", "Which websites the checks may read and how much to trust them. Click a "
                                        "site to mark it; marks count from the next batch on.")
    refused, cands, mine = ws.refused_sites(db), ws.candidate_sites(db), ws.marked_sites(db)
    t1, t2, t3 = st.tabs([f"🚫 Could not be read ({len(refused)})", f"⭐ Possibly good ({len(cands)})",
                          f"📝 Your websites ({len(mine)})"])
    with t1:
        st.caption("Sites that refused or failed when the checks tried to read them. PDFs are in the Book library.")
        data_table(refused, key="ws_refused", search="🔎 Search sites or problems",
                   columns={"site": TEXT("Site", width="medium"), "problem": TEXT("Problem", width="large"),
                            "example": TEXT("Example page", width="medium")},
                   on_open=lambda row, _o: website_dialog(refused[row]["site"], refused[row]["example"]))
    with t2:
        st.caption("Sites not on the built-in list that gave quotes, most first — they count as T until you choose. "
                   "*Pages judged weak*: quiz, content farm, forum or another subject.")
        data_table(cands, key="ws_cands", search="🔎 Search sites",
                   columns={"site": TEXT("Site", width="medium"), "example": TEXT("Example page", width="medium")},
                   on_open=lambda row, _o: website_dialog(cands[row]["site"], cands[row]["example"]))
    with t3:
        c = st.columns([2, 6])
        if c[0].button("➕ Add a website", type="primary", width="stretch"):
            add_website_dialog()
        c[1].caption("A site you add counts with the trust you give it when a search finds it (it is not searched "
                     "on purpose).")
        data_table(mine, key="ws_mine", search="🔎 Search your sites",
                   columns={"site": TEXT("Site", width="medium"), "note": TEXT("Note", width="large")},
                   on_open=lambda row, _o: website_dialog(mine[row]["site"], None))


@st.dialog("Add a website", on_dismiss="rerun")
def add_website_dialog() -> None:
    """A site the person knows: address and trust."""
    from qv.services import websites as ws
    site = st.text_input("Website", placeholder="e.g. alislam.org or https://www.example.org/page")
    choice = st.selectbox("Trust", ["P", "S", "T", "X"], index=1, format_func=TIER_LABEL.get)
    note = st.text_input("Note (optional)", placeholder="why, or what it is good for")
    if st.button("Add", type="primary", disabled=not site):
        try:
            m = ws.mark(db, site, "dont_use" if choice == "X" else "use", tier=None if choice == "X" else choice,
                        note=note)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.toast(f"{m.domain}: {ws.ACTION_LABEL[m.action]}")
        st.rerun()


@st.dialog("Website", width="large", on_dismiss="rerun")
def website_dialog(domain: str, example: str | None) -> None:
    """One site: its current state and the buttons to mark it."""
    from qv.services import websites as ws
    reg = ws.registry_with_marks(db)
    st.markdown(f"#### {domain}")
    st.markdown(f"Trust now: **{TIER_LABEL[reg.tier(domain)]}**"
                + (" · **not read for now**" if reg.is_skipped(domain) else "")
                + f" · {ws.passages_count(db, domain)} quote(s) stored from it"
                + (f"  \nExample page: [{example}]({example})" if example else "")
                + f"  \nWebsite: [https://{domain}](https://{domain})")
    hist = ws.mark_history(db, domain)
    if hist:
        st.caption("Your marks: " + " · ".join(f"{h.when} **{ws.ACTION_LABEL[h.action]}**"
                                               + (f" {h.tier}" if h.tier else "")
                                               + (f" ({h.note})" if h.note else "") for h in hist))
    note = st.text_input("Note (optional)", key=f"ws_note_{domain}", placeholder="Note (optional)")
    tier = st.selectbox("Trust (for ✅ Use)", ["P", "S", "T"], index=1, key=f"ws_tier_{domain}",
                        format_func=TIER_LABEL.get)
    c = st.columns(4)
    for col, action, label in ((c[0], "use", "✅ Use"), (c[1], "needs_access", "🔑 Needs access"),
                               (c[2], "dont_use", "⛔ Don't use"), (c[3], "clear", "↩ Clear my mark")):
        if col.button(label, key=f"ws_{action}_{domain}", width="stretch", type="primary" if action == "use"
                      else "secondary"):
            ws.mark(db, domain, action, tier=tier if action == "use" else None, note=note)
            st.toast(f"{domain}: {ws.ACTION_LABEL[action]}")
            st.rerun()


# --- navigation ----------------------------------------------------------------------------
PAGES = {
    "overview": st.Page(page_overview, title="Overview", icon=":material/dashboard:", default=True),
    "import": st.Page(page_import, title="Import a file", icon=":material/upload_file:", url_path="import"),
    "validate": st.Page(page_validate, title="Validate", icon=":material/fact_check:", url_path="validate"),
    "daily": st.Page(page_daily, title="Daily run", icon=":material/schedule:", url_path="daily"),
    "review": st.Page(page_review, title="Review", icon=":material/rate_review:", url_path="review"),
    "export": st.Page(page_export, title="Export", icon=":material/download:", url_path="export"),
    "batches": st.Page(page_batches, title="Batches", icon=":material/list_alt:", url_path="batches"),
    "files": st.Page(page_files, title="Files & versions", icon=":material/folder:", url_path="files"),
    "library": st.Page(page_library, title="Book library", icon=":material/menu_book:", url_path="library"),
    "websites": st.Page(page_websites, title="Websites", icon=":material/language:", url_path="websites"),
    "usage": st.Page(page_usage, title="Usage & quota", icon=":material/data_usage:", url_path="usage"),
}
SECTIONS = {
    "": ["overview"],
    "Files": ["import"],
    "Check questions": ["validate", "daily", "review", "export"],
    "Advanced": ["batches", "files", "library", "websites", "usage"],
}
#: Pages that work on one file show the "Working on" bar.
WITH_FILE = {"overview", "validate", "review", "export", "batches"}

nav = st.navigation({section: [PAGES[k] for k in keys] for section, keys in SECTIONS.items()})
st.markdown(CSS, unsafe_allow_html=True)

# which file: a pending switch (from a table click or an import), the address (?file=…), or the first one
all_names = workflow.dataset_names(db, include_eval=True)
if "pending_dataset" in st.session_state:
    st.session_state.dataset = st.session_state.pop("pending_dataset")
elif "dataset" not in st.session_state and st.query_params.get("file") in all_names:
    st.session_state.dataset = st.query_params["file"]
if str(st.session_state.get("dataset", "")).startswith("eval-"):
    st.session_state.show_eval = True
names = workflow.dataset_names(db, include_eval=st.session_state.get("show_eval", False))
if names and st.session_state.get("dataset") not in names:
    st.session_state.dataset = names[0]

page_key = next((k for k, p in PAGES.items() if p.url_path == nav.url_path), "overview")
if page_key in WITH_FILE:
    file_header()
if st.session_state.get("dataset"):
    st.query_params["file"] = st.session_state.dataset
nav.run()
