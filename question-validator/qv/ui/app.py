"""Web page (Streamlit). Run with `qv ui`, or double-click `Start Question Validator.command`.

Pages: Overview · 1 Import · 2 Validate · 3 Review · 4 Export · Advanced, for the file chosen under
"Working on" in the sidebar. Queries and writes live in qv.services; this file only lays them out.
Long work (a batch) runs as a separate `qv next` process, so the page can be closed while it works.

Every table goes through `data_table` (our own component in qv/ui/table.py) so all tables look and behave the
same: header stays put, row count, click anywhere on a row to open it, nothing editable.
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from qv.config import Settings, available_profiles, load_profile, load_research_config
from qv.db.session import Database
from qv.pipeline.priority import SIGNALS
from qv.services import views, worker, workflow
from qv.services.workflow import STATUS_LABEL
from qv.ui.table import render_table

st.set_page_config(page_title="Question Validator", page_icon="✅", layout="wide")

ROW_PX, HEADER_PX = 35, 36
CSS = f"""
<style>
/* Sidebar menu: a little more room per item */
[data-testid="stSidebar"] [data-testid="stPageLink"] a {{ padding: 0.35rem 0.6rem; }}
.qv-file {{ font-size: 0.85rem; color: #555; line-height: 1.35; margin: -0.4rem 0 0.6rem 0; }}
</style>
"""

STATUS_ICON = {"to_review": "🔍", "specialist": "🎓", "no_evidence": "❓", "spot_check": "🎲", "verified": "✅",
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
               "no_evidence": "❓ Not enough evidence", "spot_check": "🎲 Spot check", "verified": "✅ Verified",
               "decided": "👍 Decided by you"}
GROUP_HELP = {
    "all": "Every question that has been checked, whatever the result.",
    "to_review": "The sources disagree with the answer, or the question is unclear. Decide what to do.",
    "specialist": "Religious or doctrinal: needs the verse or an official Ahmadiyya source. Download the list "
                  "for your reviewer, then enter their answer here.",
    "no_evidence": "Nothing reliable was found. Keep it if you know it is right, edit it, or leave it for later.",
    "spot_check": "Verified automatically; a few are picked at random so you can check the checker.",
    "verified": "Verified automatically. Open any of them to look at the sources the result rests on.",
    "decided": "Questions you decided. Open one to see or change your decision.",
}
LEGEND = """
**Verdicts** — VERIFIED · INCORRECT · OUTDATED · CONTESTED · AMBIGUOUS · UNVERIFIED (not enough evidence; not
the same as wrong).

**Evidence for the answer** — STRONG: meets the bar for this kind of fact (e.g. the verse itself for a Qur'an
question; the official record or two independent expert sources for a record) · MODERATE: some independent
support, below the bar · WEAK: one source · NONE.

**Answer found without the key** — the evidence was read by a step that was *not told* the expected answer.
"same" is the strongest sign the answer is right; "different" is the strongest sign of an error.

**Sources** — P primary (the text itself, the official record, the author's own book) · S expert (scholarly,
reputable news, official histories) · T encyclopaedia / summary · X not evidence (quiz sites, forums). A
*frame authority* is an official source of the edition's tradition (e.g. alislam.org).

**Origins (C1, C2 …)** — passages that trace back to the same source count once, however many sites repeat it.
"""


@st.cache_resource
def get_db() -> Database:
    """One database handle per server process."""
    return Database(Settings().database_url)


db = get_db()
settings = Settings()


# --- shared pieces ------------------------------------------------------------------------

def data_table(rows: list[dict] | pd.DataFrame, *, key: str | None = None, select: bool = False,
               columns: dict | None = None, max_rows: int = 12, highlight: int | None = None) -> int | None:
    """Every table on the page: same look, height that fits, row count, optional click-a-row.

    With select=True a click anywhere on a row picks it and highlights the whole row (no tick boxes, nothing
    editable). Returns the picked position, else None. `highlight` marks a row until one is clicked.
    """
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if df.empty:
        st.caption("Nothing to show.")
        return None
    shown = min(len(df), max_rows)
    pick = render_table(df, key=key, select=select, columns=columns, height=HEADER_PX + ROW_PX * shown + 16,  # + room for a sideways scrollbar
                        highlight=highlight)
    note = f"{len(df)} row{'s' if len(df) != 1 else ''}"
    if len(df) > max_rows:
        note += " — scroll the table to see all"
    if select:
        note += " · click a row to open it"
    st.caption(note)
    return pick


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


def sources(run_id: int, question_id: int, *, full: bool = False) -> None:
    """The quotes a result rests on, grouped by page (full=True: every page, with context)."""
    detail = views.question_detail(db, run_id, question_id)
    docs = [d for d in detail["documents"] if full or d["passages"]]
    if not docs:
        st.caption("No quotes were found.")
    for d in docs:
        badge = TIER_LABEL.get(d["effective_tier"] or d["registry_tier"], "?")
        purpose = "for the question" if d["mode"] == "A" else "for the note"
        with st.expander(f"{d['title'] or d['url']} — {badge}{' · frame authority' if d['frame_authority'] else ''}"
                         f" · {purpose} · {d['grounded']} quote(s)", expanded=not full and d["mode"] == "A"):
            st.markdown(f"[{d['url']}]({d['url']}) · read {d['fetched']} · {d['page_kind'] or '-'} · "
                        f"{STATUS_TEXT.get(d['status'], d['status'])}"
                        + (f" · {d['dropped']} quote(s) rejected (not found word for word)" if d["dropped"] else ""))
            if d["concerns"]:
                st.warning("Concerns: " + "; ".join(d["concerns"]))
            if d["about_right_subject"] is False:
                st.error("This page is about a different subject; its quotes are not used.")
            for p in d["passages"]:
                st.markdown(f"> {p['quote']}")
                meta = [f"about {p['target']}"]
                if p["asserted_answer"]:
                    meta.append(f"says the answer is **{p['asserted_answer']}**"
                                + (f" (option {p['matches_option']})" if p["matches_option"] else ""))
                for k, label in (("qualifiers", "only if"), ("as_of", "as of"), ("origin", "credits")):
                    if p[k]:
                        meta.append(f"{label}: {p[k]}")
                st.caption(f"{p['short_id']}" + (f" · origin {p['cluster']}" if p["cluster"] else "")
                           + " · " + " · ".join(meta))
            if full and d["passages"] and st.checkbox("Show the quotes in their page",
                                                      key=f"ctx{run_id}-{d['doc_id']}{d['mode']}"):
                st.markdown(highlight(d["text"], d["passages"]), unsafe_allow_html=True)


# ===========================================================================================
def page_overview() -> None:
    """Every file with its progress, and the next step for the current one."""
    st.title("Overview")
    cards = views.dataset_cards(db, include_eval=st.session_state.get("show_eval", False))
    if not cards:
        st.info("Nothing imported yet. Import a question file (one per game edition) to begin.")
        if st.button("Go to Import", type="primary"):
            st.switch_page(PAGES["import"])
        return
    st.markdown("Your question files — one per game edition. **Click a row** to work on that file.")
    here = next((i for i, c in enumerate(cards) if c["file"] == st.session_state.get("dataset")), None)
    pick = data_table(cards, key="overview_files", select=True, highlight=here,
                      columns={"file": TEXT("File"), "source file": TEXT("Source file")})
    if pick is not None and pick != st.session_state.get("overview_last_pick"):  # a new click, not an old one
        st.session_state.overview_last_pick = pick
        if cards[pick]["file"] != st.session_state.get("dataset"):
            st.session_state.pending_dataset = cards[pick]["file"]
            st.rerun()
    name = current()
    st.subheader(f"Working on: {name}")
    c = progress(workflow.question_states(db, name))
    cols = st.columns(4)
    cols[0].metric("✅ Verified / kept", c["verified"] + c["approved"] + c["edited"])
    cols[1].metric("🔍 To look at", sum(c[k] for k in workflow.REVIEW_STATUSES))
    cols[2].metric("⏳ Still to check", c["not_checked"] + c["failed"] + c["in_progress"])
    cols[3].metric("🛑 Format errors", c["format_error"])
    next_step(name)
    with st.expander("How it works"):
        st.markdown("1. **Import** a question file (the game's CSV format) — its format is checked first.\n"
                    "2. **Validate**: press *Validate next batch*. The free AI limits allow about 25 questions a "
                    "day; when a batch stops, press it again later. Finished work is never repeated.\n"
                    "3. **Review** the results: look at what needs a person, and at any verified question you "
                    "want to double-check. Keep, edit, ask the specialist or remove.\n"
                    "4. **Export** the corrected file and copy it into the game.")


# ===========================================================================================
def page_import() -> None:
    """Upload, format check with what to do, import."""
    from qv.services import datasets as ds_service
    from qv.services.import_fixes import suggest_fixes
    from qv.services.import_help import hint
    st.title("1 · Import a question file")
    st.markdown("Use the game's CSV format — one question per line. Columns (any order): **id, question, type, "
                "answer**, opt_a, opt_b, opt_c, opt_d, difficulty, category, subcategory, topic, note. "
                "The first four are required. For `multi`, the answer is the option number 1–4.")
    up = st.file_uploader("Question file (.csv)", type=["csv"])
    existing = workflow.dataset_names(db, include_eval=True)
    target = st.radio("Import as", ["A new version of an existing file", "A new file"], horizontal=True,
                      index=0 if existing else 1, disabled=not existing)
    dataset = st.session_state.get("dataset")
    if target.startswith("A new version") and existing:
        name = st.selectbox("Which file", existing, index=existing.index(dataset) if dataset in existing else 0)
        profile = workflow.dataset_profile(db, name) or "general"
        st.caption(f"Profile: *{profile}* · questions with the same id and text keep their results and decisions.")
    else:
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", placeholder="e.g. world-tour", help="Short name, used in commands")
        profiles = available_profiles()
        profile = c2.selectbox("Edition profile", profiles,
                               index=profiles.index("general") if "general" in profiles else 0,
                               help="Decides the audience and, for Swab Quest and Prophets' Stories, the "
                                    "Ahmadiyya understanding")
    if up is None or not name:
        return
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
                               columns={"change": TEXT("Change", width="large")})
                if st.button("Fix them for me", type="primary"):
                    st.session_state[fixed_key] = fx.data
                    st.rerun()
    result = ds_service.check_bytes(data, load_profile(profile))
    rep = result.report
    errors = [i for i in rep.issues if i.severity == "error"]
    warnings = [i for i in rep.issues if i.severity == "warning"]
    st.subheader(f"Format check: {len(result.questions)} questions")
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
        for (code, sev), items in sorted(groups.items(), key=lambda kv: ["error", "warning", "info"].index(kv[0][1])):
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
                           columns={"problem": TEXT("Problem", width="large"),
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
    """Choose questions, start / continue a batch, follow it."""
    name = current()
    st.title("2 · Validate")
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
    tab_go, tab_why = st.tabs(["Next batch", "Fact-heavy wording (optional order)"])
    with tab_go:
        st.markdown("**Which questions** (leave empty for all)")
        f = st.columns(4)
        cats = sorted({s.category for s in states if s.category})
        sel_cats = f[0].multiselect("Category", cats)
        subs = sorted({s.subcategory for s in states if s.subcategory and (not sel_cats or s.category in sel_cats)})
        sel_subs = f[1].multiselect("Subcategory", subs)
        topics = sorted({s.topic for s in states if s.topic and (not sel_cats or s.category in sel_cats)
                         and (not sel_subs or s.subcategory in sel_subs)})
        sel_topics = f[2].multiselect("Topic", topics)
        diffs = sorted({s.difficulty for s in states if s.difficulty})
        sel_diffs = f[3].multiselect("Difficulty", diffs)
        g = st.columns([2, 1])
        order = g[0].selectbox("Order", list(workflow.ORDERS), format_func=workflow.ORDERS.get,
                               help="Questions you edited always come first. 'Fact-heavy wording' is explained "
                                    "in the second tab.")
        default = load_research_config().batch_size
        today = workflow.suggested_batch_size(db, default)
        size = g[1].number_input("Questions in this batch", min_value=1, max_value=200, value=today or default,
                                 help=f"Suggested from today's free limits (at most {default}). A batch stops by "
                                      "itself when a free limit is reached.")
        sel = workflow.Selection(categories=tuple(sel_cats), subcategories=tuple(sel_subs), topics=tuple(sel_topics),
                                 difficulties=tuple(sel_diffs), order=order)
        plan = workflow.plan_next_batch(db, name, sel, int(size))
        if today == 0 and plan.action != "nothing":
            reset = workflow.next_reset_local()
            st.warning(f"Today's free AI requests are used up. They come back at **{reset:%H:%M} ({reset:%A})**.")
        st.markdown(f"**{plan.message}**")
        if plan.questions:
            data_table([{"id": q.ext_id, "difficulty": q.difficulty, "question": q.question,
                         "category": path(q.category, q.subcategory, q.topic),
                         **({"why first": ", ".join(q.priority_reasons)} if order == "risk" else {})}
                        for q in plan.questions], key=f"plan_{name}", columns=COLS_QUESTION, max_rows=8)
        label = "Continue the stopped batch" if plan.action == "resume" else "Validate next batch"
        if running:
            st.button(label, disabled=True, help="A batch is already running")
        elif today == 0 and plan.action != "nothing":
            st.button(label, disabled=True, help="Today's free AI requests are used up")
        elif plan.action != "nothing" and st.button(label, type="primary"):
            args = ["--size", str(int(size)), "--order", sel.order]
            for flag, values in (("--category", sel.categories), ("--subcategory", sel.subcategories),
                                 ("--topic", sel.topics), ("--difficulty", sel.difficulties)):
                for v in values:
                    args += [flag, v]
            worker.start_background(settings.data_dir, name, args)
            st.rerun()
        st.caption(f"Terminal: `qv next {name}` does the same. Run it again whenever it stops.")
        daily_box(name)
        if c["format_error"]:
            st.warning(f"{c['format_error']} question(s) have format errors and are skipped — fix them in the file "
                       "and import it again.")
    with tab_why:
        st.markdown(
            "**What this is:** a way to check *fact-heavy* questions first. It reads only the wording — no AI, no "
            "sources — and counts the kinds of wording where quiz answers most often turn out wrong.\n\n"
            "**What it is not:** it does **not** say how likely an answer is wrong. A question with many points "
            "can be perfectly right, and a question with none can be wrong. Every question still gets the full "
            "check; this only changes the order. If you prefer, order by difficulty instead.")
        data_table([{"signal": r, "points": pts, "meaning": m} for r, pts, m in SIGNALS],
                   columns={"meaning": TEXT("Meaning", width="large")}, max_rows=10)
        st.caption("4 points or more = high · 2–3 = medium · 0–1 = low")
        rows = [{"id": s.ext_id, "points": s.priority_score, "level": s.priority_level,
                 "why": ", ".join(s.priority_reasons) or "—", "difficulty": s.difficulty, "question": s.question}
                for s in sorted(states, key=lambda s: (-s.priority_score, s.row_no)) if s.status in workflow.CHECKABLE]
        st.markdown(f"**Questions not checked yet, by points** ({len(rows)})")
        data_table(rows, key=f"risk_{name}", columns={**COLS_QUESTION, "why": TEXT("Why", width="medium")})


def daily_box(name: str) -> None:
    """Turn the automatic daily batch on or off."""
    from qv.services import daily
    from qv.services.workflow import next_reset_local
    stat = daily.status(settings.data_dir)
    title = (f"🔁 Every day by itself: **on** at {stat.settings.time_text} — {', '.join(stat.settings.datasets)}"
             if stat.on else "🔁 Every day by itself: off")
    with st.expander(title):
        st.markdown("Your Mac validates the next batch every day — the same as pressing *Validate next batch* — "
                    "for the files you choose, in that order, until the day's free requests are used up. If the "
                    "Mac is asleep at that time, it runs when the Mac wakes up. Results show up here as usual.")
        names = workflow.dataset_names(db)
        chosen = [d for d in stat.settings.datasets if d in names] or [name]
        files = st.multiselect("Files, in this order", names, default=chosen, key="daily_files")
        reset = next_reset_local()
        default = stat.settings if stat.on else daily.DailySettings(
            hour=((reset.hour * 60 + reset.minute + 15) // 60) % 24, minute=(reset.minute + 15) % 60)
        from datetime import time as _time
        at = st.time_input("Time", value=_time(default.hour, default.minute), step=900,
                           help=f"The free limits reset at {reset:%H:%M} your time; a little after that is best.")
        b1, b2 = st.columns(2)
        if b1.button("Save and turn on" if not stat.on else "Save changes", type="primary", disabled=not files):
            try:
                daily.turn_on(settings.data_dir, daily.DailySettings(list(files), at.hour, at.minute))
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
            else:
                st.rerun()
        if stat.on and b2.button("Turn off"):
            daily.turn_off()
            st.rerun()
        text = worker.tail(stat.log, 8)
        if text:
            st.markdown("**Last daily run**")
            st.code(text, language=None)
        st.caption("Terminal: `qv auto status` · `qv auto on --file <name>` · `qv auto off` · `qv auto run` (run "
                   "today's work now).")


# ===========================================================================================
def page_review() -> None:
    """Every checked question in a table; click one to see its result and decide."""
    name = current()
    st.title("3 · Review")
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
    f = st.columns([3, 2])
    search = f[0].text_input("Search", placeholder="words in the question or answer, or an id",
                             label_visibility="collapsed")
    cats = sorted({s.category for s in groups[group] if s.category})
    sel_cats = f[1].multiselect("Category", cats, placeholder="All categories", label_visibility="collapsed")
    items = [s for s in groups[group] if (not sel_cats or s.category in sel_cats)
             and (not search or search.lower() in f"{s.ext_id} {s.question} {s.answer_text}".lower())]
    items.sort(key=lambda s: (s.later, s.row_no))
    if group == "specialist" and items:
        from qv.services.exports import results_csv
        st.download_button("⬇ Download the list for your specialist (CSV)", results_csv(db, items),
                           file_name=f"{name}-for-specialist.csv", mime="text/csv")
    pick = data_table([{"status": status_text(s) + (" · later" if s.later else ""), "id": s.ext_id,
                        "question": s.question, "answer": s.answer_text, "result": s.verdict,
                        "your decision": s.decision, "category": path(s.category, s.subcategory, s.topic)}
                       for s in items], key=f"review_{name}_{group}_{search}_{','.join(sel_cats)}", select=True,
                      columns=COLS_QUESTION)
    if not items:
        return
    if pick is None or pick >= len(items):
        st.info("👆 Click a row in the table to see its result and decide.")
        return
    review_detail(name, items[pick])


def review_detail(name: str, item: workflow.QuestionState) -> None:
    """The result of one question and the decision buttons."""
    with st.container(border=True):
        st.markdown(f"#### Reviewing #{item.ext_id} · {status_text(item)}")
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
        if v:
            verdict_box(v)
            tab_why, tab_src = st.tabs(["Why", "Sources"])
            with tab_why:
                st.markdown("\n".join(f"- {r}" for r in v["reasons_json"]))
                issues = (v["quality_json"] or {}).get("issues", [])
                if issues:
                    st.markdown("**Quality notes**\n" + "\n".join(
                        f"- {i['type'].replace('_', ' ')} ({i['severity']}): {i['detail']}" for i in issues))
            with tab_src:
                sources(item.run_id, v["question_id"])
        hist = workflow.decision_history(db, name, item.ext_id)
        if hist:
            st.caption("Your decisions: " + " · ".join(f"{h['when']} **{h['action']}**"
                                                       + (f" ({h['comment']})" if h["comment"] else "") for h in hist))

        st.markdown("**Your decision**")
        comment = st.text_input("Comment (optional)", key=f"comment_{item.ext_id}", label_visibility="collapsed",
                                placeholder="Comment (optional)")
        b = st.columns(5)

        def decide(action: str, changes: dict | None = None) -> None:
            workflow.record_decision(db, name, item.ext_id, action, changes=changes, comment=comment)
            st.toast(f"#{item.ext_id}: {action}")

        if b[0].button("✔ Keep", help="Keep as is: you checked it and it is right", width="stretch"):
            decide("keep")
            st.rerun()
        if b[1].button("✎ Edit", help="Change the question, options, answer or note", width="stretch"):
            st.session_state[f"editing_{item.ext_id}"] = True
        if b[2].button("🎓 Specialist", help="Ask the specialist: puts it on the list for your reviewer", width="stretch"):
            decide("specialist")
            st.rerun()
        if b[3].button("✖ Remove", help="Leave it out of the exported file", width="stretch"):
            decide("remove")
            st.rerun()
        if b[4].button("⏭ Later", help="Moves it to the end of the list", width="stretch"):
            decide("later")
            st.rerun()
        if st.session_state.get(f"editing_{item.ext_id}"):
            edit_form(item, v)


def edit_form(item: workflow.QuestionState, v: dict | None) -> None:
    """Change question, options, answer or note (optionally starting from the suggestion)."""
    name = st.session_state.dataset
    sugg_q = (v or {}).get("suggested_question") or ""
    sugg_a = (v or {}).get("suggested_answer") or ""
    use = st.checkbox("Start from the suggestion", value=bool(sugg_q or sugg_a), disabled=not (sugg_q or sugg_a))
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
                st.session_state[f"editing_{item.ext_id}"] = False
                st.toast(f"#{item.ext_id}: edited")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


# ===========================================================================================
def page_export() -> None:
    """The three downloads and what to do with them."""
    from qv.services.exports import ExportError, workflow_export
    name = current()
    st.title("4 · Export")
    states = workflow.question_states(db, name)
    c = workflow.counts(states)
    open_ = sum(c[k] for k in workflow.REVIEW_STATUSES) + c["not_checked"] + c["failed"]
    m = st.columns(5)
    m[0].metric("Questions", len(states))
    m[1].metric("✅ Verified", c["verified"])
    m[2].metric("👍 Kept / ✏️ edited", c["approved"] + c["edited"])
    m[3].metric("✖️ Removed", c["removed"])
    m[4].metric("Still open", open_)
    if open_:
        st.info("You can export at any time: open questions stay unchanged in the corrected file and are left out "
                "of the verified-only file.")
    downloads = [
        ("corrected", "⬇ Corrected file", "The whole file with your edits applied and removed questions left out. "
                                         "Same ids, same order, format checked again. **This one goes into the "
                                         "game.**"),
        ("verified", "⬇ Verified only", "Only questions that were verified or that you kept or edited."),
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
    st.markdown("#### Then, in the game")
    st.markdown("Copy the corrected file to `game_editions/<edition>/questions.csv`, run `npm run build:content` and "
                "play a round. The validator never writes into the game's folders itself. When you change questions "
                "in the game later, import the file again: only new and changed questions are checked.")


# ===========================================================================================
def page_advanced() -> None:
    """Detailed views: checked questions with every source, files and format problems, quota and usage."""
    st.title("Advanced")
    st.caption("Detailed views for checking how the validator works. Everything here also exists as a `qv` "
               "command; the database is described in DATABASE.md.")
    dataset = st.session_state.get("dataset")
    tab_q, tab_f, tab_u = st.tabs(["Checked questions (by batch)", "Files & format", "Usage & quota"])

    with tab_q:
        with st.expander("What the words mean"):
            st.markdown(LEGEND)
        runs = views.runs_overview(db)
        mine = st.toggle(f"Only batches of {dataset}", value=True) if dataset else False
        runs = [r for r in runs if not mine or r["dataset"] == dataset]
        st.markdown("**Batches** — click one to see its questions")
        r_pick = data_table([{"batch": r["run"], "file": r["dataset"], "version": r["version"], "started": r["created"],
                              "status": r["status"], "done": r["done"], "failed": r["failed"],
                              "left": r["pending"] + r["stopped"], "stopped because": r["stop_reason"]} for r in runs],
                            key=f"adv_runs_{mine}", select=True, max_rows=6,
                            columns={"stopped because": TEXT("Stopped because", width="large")})
        if r_pick is not None:
            run_id = runs[r_pick]["run"]
            qs = views.run_questions(db, run_id)
            st.markdown(f"**Questions in batch {run_id}** — click one to see everything about it")
            q_pick = data_table(qs, key=f"adv_q_{run_id}", select=True, columns=COLS_QUESTION)
            if q_pick is not None:
                question_full(run_id, qs[q_pick]["_qid"])

    with tab_f:
        overview = views.datasets_overview(db)
        st.markdown("**Imported files and versions** — click one to see its questions and format problems")
        v_pick = data_table(overview, key="adv_versions", select=True, max_rows=8,
                            columns={"version_id": None})
        if v_pick is not None:
            vid = overview[v_pick]["version_id"]
            t1, t2 = st.tabs(["Questions", "Format problems"])
            with t1:
                rows = views.version_questions(db, vid)
                text = st.text_input("Filter (text in question, key or category)")
                if text:
                    t = text.lower()
                    rows = [r for r in rows if t in r["question"].lower() or t in r["key"].lower()
                            or t in r["category"].lower()]
                data_table(rows, key=f"adv_vq_{vid}", columns={**COLS_QUESTION, "_qid": None})
            with t2:
                issues = views.version_issues(db, vid)
                sev = st.multiselect("Severity", ["error", "warning", "info"], default=["error", "warning"])
                data_table([i for i in issues if i["severity"] in sev], key=f"adv_vi_{vid}",
                           columns={"message": TEXT("Message", width="large")})

    with tab_u:
        st.markdown("**Free quota left now**")
        data_table(views.quota_rows(db), max_rows=15)
        st.caption(f"Gemini's daily limits come back at {workflow.next_reset_local():%H:%M} local time.")
        st.markdown("**Calls so far** (free tiers only: cost is always $0)")
        data_table(views.usage_summary(db), max_rows=15)


def question_full(run_id: int, question_id: int) -> None:
    """Everything about one checked question: result, every source, research plan."""
    detail = views.question_detail(db, run_id, question_id)
    q = detail["question"]
    with st.container(border=True):
        st.markdown(f"#### #{q['id']} {q['question']}")
        if q["type"] == "multi":
            st.markdown("  ·  ".join(f"**{'ABCD'[i]}.** {o}" for i, o in enumerate(q["options"]) if o))
        st.markdown(f"**Expected answer:** {q['key']}" + (f"  ·  **Note:** {q['note']}" if q["note"] else ""))
        v = views.question_verdict(db, run_id, q["id"])
        if v is None:
            st.info(f"Not judged in this batch (`qv judge {run_id}` gives a verdict).")
        else:
            verdict_box(v)
            st.markdown("**Why**\n" + "\n".join(f"- {r}" for r in v["reasons_json"]))
        st.markdown("**Every page that was read**")
        sources(run_id, question_id, full=True)
        with st.expander("How the research was planned (S1a / S1b)"):
            st.json({k: s["output"] for k, s in detail["stages"].items() if k in ("s1a", "s1b")})
        with st.expander("Research statistics"):
            st.json(detail["stats"])


# --- navigation ----------------------------------------------------------------------------
PAGES = {
    "overview": st.Page(page_overview, title="Overview", icon=":material/dashboard:", default=True),
    "import": st.Page(page_import, title="1 · Import", icon=":material/upload_file:", url_path="import"),
    "validate": st.Page(page_validate, title="2 · Validate", icon=":material/fact_check:", url_path="validate"),
    "review": st.Page(page_review, title="3 · Review", icon=":material/rate_review:", url_path="review"),
    "export": st.Page(page_export, title="4 · Export", icon=":material/download:", url_path="export"),
    "advanced": st.Page(page_advanced, title="Advanced", icon=":material/tune:", url_path="advanced"),
}
nav = st.navigation(list(PAGES.values()), position="hidden")
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

with st.sidebar:
    st.markdown("## ✅ Question Validator")
    if names:
        st.selectbox("Working on", names, key="dataset")
        card = {c["file"]: c for c in views.dataset_cards(db, include_eval=True)}.get(st.session_state.dataset)
        if card:
            st.markdown(f"<div class='qv-file'>📄 <b>{html.escape(card['source file'])}</b> · version "
                        f"{card['version']}<br>imported {card['imported']} · {card['questions']} questions<br>"
                        f"profile <i>{html.escape(card['profile'])}</i></div>", unsafe_allow_html=True)
    else:
        st.info("No file yet — start with **Import**.")
    for page in PAGES.values():
        st.page_link(page, label=page.title, icon=page.icon)
    batch = worker.status(settings.data_dir)
    if batch.running:
        st.success(f"⏳ Checking **{batch.dataset}** (since {batch.started})")
    st.divider()
    st.toggle("Show evaluation sets", key="show_eval", help="The eval-… datasets used to measure the validator")

if st.session_state.get("dataset"):
    st.query_params["file"] = st.session_state.dataset
nav.run()
