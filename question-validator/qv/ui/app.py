"""Web view (Streamlit). Run with `qv ui`, or double-click `Start Question Validator.command`.

Four steps — Import · Validate · Review · Export — on the file chosen under "Working on", plus an
Overview and an Advanced area with the detailed views. Queries and writes live in qv.services; this
file only lays them out. Long work (a batch) runs as a separate `qv next` process, so the page can be
closed while it works.
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from qv.config import Settings, available_profiles, load_profile, load_research_config
from qv.db.session import Database
from qv.services import views, worker, workflow
from qv.services.workflow import STATUS_LABEL

st.set_page_config(page_title="Question Validator", page_icon="✅", layout="wide")

PAGES = ["Overview", "1 · Import", "2 · Validate", "3 · Review", "4 · Export", "Advanced"]
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
GROUP_HELP = {
    "to_review": "The sources disagree with the answer, or the question is unclear. Decide what to do.",
    "specialist": "Religious or doctrinal: needs the verse or an official Ahmadiyya source. Download the list "
                  "for your reviewer, then enter their answer here.",
    "no_evidence": "Nothing reliable was found. Keep it if you know it is right, edit it, or leave it for later.",
    "spot_check": "Verified automatically; a few are shown at random so you can check the checker.",
    "decided": "Questions you already decided. Pick one to change your decision.",
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

**Priority** — a quick guess from the wording (no AI): numbers and dates, "most / first / only" claims, facts
that change over time, references and quotes, notes with their own claims, format warnings and hard questions
come first. Edited questions always come first.
"""


@st.cache_resource
def get_db() -> Database:
    """One database handle per server process."""
    return Database(Settings().database_url)


def table(rows: list[dict], hide: tuple[str, ...] = ("_qid",)) -> pd.DataFrame:
    """DataFrame without internal columns."""
    df = pd.DataFrame(rows)
    return df.drop(columns=[c for c in hide if c in df.columns]) if not df.empty else df


def go(page: str | None = None, dataset: str | None = None) -> None:
    """Button callback: switch page and/or file."""
    if page:
        st.session_state.page = page
    if dataset:
        st.session_state.dataset = dataset


def highlight(text: str, passages: list[dict], context: int = 400) -> str:
    """HTML excerpts of a document around each grounded passage, the passage marked."""
    parts = []
    for p in passages:
        a, b = p["start"], p["end"]
        lo, hi = max(0, a - context), min(len(text), b + context)
        parts.append(f"<p style='font-size:0.9em'>…{html.escape(text[lo:a])}"
                     f"<mark>{html.escape(text[a:b])}</mark>{html.escape(text[b:hi])}…</p>")
    return "<hr>".join(parts)


db = get_db()
settings = Settings()

# --- sidebar: which file, which step ------------------------------------------------------
SLUG = {"Overview": "overview", "1 · Import": "import", "2 · Validate": "validate", "3 · Review": "review",
        "4 · Export": "export", "Advanced": "advanced"}
names = workflow.dataset_names(db, include_eval=st.session_state.get("show_eval", False))
if "page" not in st.session_state:  # first load: the address (?file=…&page=…) remembers where you were
    wanted = st.query_params.get("page")
    st.session_state.page = next((p for p, slug in SLUG.items() if slug == wanted),
                                 "Overview" if names else "1 · Import")
    if st.query_params.get("file") in workflow.dataset_names(db, include_eval=True):
        st.session_state.dataset = st.query_params["file"]
        st.session_state.show_eval = st.query_params["file"].startswith("eval-")
        names = workflow.dataset_names(db, include_eval=st.session_state.show_eval)
if names and st.session_state.get("dataset") not in names:
    st.session_state.dataset = names[0]

with st.sidebar:
    st.title("✅ Question Validator")
    if names:
        st.selectbox("Working on", names, key="dataset")
        cards = {c["file"]: c for c in views.dataset_cards(db, include_eval=True)}
        card = cards.get(st.session_state.dataset)
        if card:
            st.caption(f"📄 **{card['source file']}** · version {card['version']} · imported {card['imported']}  \n"
                       f"{card['questions']} questions · profile *{card['profile']}*")
    else:
        st.info("No file yet — start with **1 · Import**.")
    st.radio("Go to", PAGES, key="page", label_visibility="collapsed")
    batch = worker.status(settings.data_dir)
    if batch.running:
        st.success(f"⏳ Checking **{batch.dataset}** (since {batch.started})")
    st.divider()
    st.toggle("Show evaluation sets", key="show_eval", help="The eval-… datasets used to measure the validator")

page = st.session_state.page
dataset = st.session_state.get("dataset")
st.query_params.update({"page": SLUG[page], **({"file": dataset} if dataset else {})})


def need_dataset() -> str:
    """The current file, or stop with a pointer to Import."""
    if not dataset:
        st.info("Import a question file first.")
        st.button("Go to 1 · Import", on_click=go, args=("1 · Import",))
        st.stop()
    return dataset


def next_step_card(name: str) -> None:
    """What to do next for a file, as one sentence and one button."""
    c = workflow.counts(workflow.question_states(db, name))
    left = c["not_checked"] + c["failed"] + c["in_progress"]
    review = sum(c[k] for k in workflow.REVIEW_STATUSES)
    running = worker.status(settings.data_dir)
    if running.running and running.dataset == name:
        st.info("⏳ A batch is being checked right now. You can close this page; come back later.")
        st.button("See progress", on_click=go, args=("2 · Validate",), type="primary")
    elif review:
        st.warning(f"👉 **Next: review {review} question(s)** that need a person.")
        st.button("Go to 3 · Review", on_click=go, args=("3 · Review",), type="primary")
    elif left:
        st.info(f"👉 **Next: validate the next batch** — {left} question(s) still to check.")
        st.button("Go to 2 · Validate", on_click=go, args=("2 · Validate",), type="primary")
    else:
        st.success("👉 **Everything is checked and decided.** Download the corrected file.")
        st.button("Go to 4 · Export", on_click=go, args=("4 · Export",), type="primary")


# ===========================================================================================
if page == "Overview":
    st.title("Overview")
    cards = views.dataset_cards(db, include_eval=st.session_state.get("show_eval", False))
    if not cards:
        st.info("Nothing imported yet. Import a question file (one per game edition) to begin.")
        st.button("Go to 1 · Import", on_click=go, args=("1 · Import",), type="primary")
        st.stop()
    st.caption("One line per question file. Pick the file to work on in the sidebar, under *Working on*.")
    st.dataframe(pd.DataFrame(cards), width="stretch", hide_index=True)
    name = need_dataset()
    st.subheader(f"{name}")
    states = workflow.question_states(db, name)
    c = workflow.counts(states)
    checkable = len(states) - c["format_error"]
    done = checkable - c["not_checked"] - c["failed"] - c["in_progress"]
    st.progress(done / max(checkable, 1), text=f"{done} of {checkable} questions checked"
                + (f" ({c['format_error']} with format errors are skipped)" if c["format_error"] else ""))
    cols = st.columns(4)
    cols[0].metric("✅ Verified / checked by you", c["verified"] + c["approved"] + c["edited"])
    cols[1].metric("🔍 To look at", sum(c[k] for k in workflow.REVIEW_STATUSES))
    cols[2].metric("⏳ Still to check", c["not_checked"] + c["failed"] + c["in_progress"])
    cols[3].metric("⚠️ Format errors", c["format_error"])
    next_step_card(name)
    with st.expander("How it works"):
        st.markdown("1. **Import** a question file (the game's CSV format) — its format is checked first.\n"
                    "2. **Validate**: press *Validate next batch*. The free AI limits allow about 25 questions a "
                    "day; when a batch stops, press it again later. Finished work is never repeated.\n"
                    "3. **Review** the questions that need a person: keep, edit, ask the specialist, remove.\n"
                    "4. **Export** the corrected file and copy it into the game.")

# ===========================================================================================
elif page == "1 · Import":
    from qv.services import datasets as ds_service
    from qv.services.import_help import hint
    st.title("1 · Import a question file")
    st.markdown("Use the game's CSV format — one question per line. Columns (any order): **id, question, type, "
                "answer**, opt_a, opt_b, opt_c, opt_d, difficulty, category, subcategory, topic, note. "
                "The first four are required. For `multi`, the answer is the option number 1–4.")
    up = st.file_uploader("Question file (.csv)", type=["csv"])
    existing = workflow.dataset_names(db, include_eval=True)
    target = st.radio("Import as", ["A new version of an existing file", "A new file"], horizontal=True,
                      index=0 if existing else 1, disabled=not existing)
    if target.startswith("A new version") and existing:
        name = st.selectbox("Which file", existing, index=existing.index(dataset) if dataset in existing else 0)
        with db.session() as s:
            from qv.db.models import Dataset
            from sqlalchemy import select
            profile = s.scalar(select(Dataset.profile).where(Dataset.name == name))
        st.caption(f"Profile: *{profile}* · questions with the same id and text keep their results.")
    else:
        c1, c2 = st.columns(2)
        name = c1.text_input("Name", placeholder="e.g. world-tour", help="Short name, used in commands")
        profiles = available_profiles()
        profile = c2.selectbox("Edition profile", profiles, index=profiles.index("general")
                               if "general" in profiles else 0,
                               help="Decides the audience and, for Swab Quest and Prophets' Stories, the "
                                    "Ahmadiyya understanding")
    if up is not None and name:
        data = up.getvalue()
        result = ds_service.check_bytes(data, load_profile(profile))
        rep = result.report
        errors = [i for i in rep.issues if i.severity == "error"]
        warnings = [i for i in rep.issues if i.severity == "warning"]
        missing_required = [i for i in errors if i.code == "missing_column"]
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
            groups = dict(sorted(groups.items(), key=lambda kv: ["error", "warning", "info"].index(kv[0][1])))
            column_titles = {("missing_column", "error"): "Missing required column",
                             ("missing_column", "warning"): "Missing columns",
                             ("unknown_column", "info"): "Columns the game does not use",
                             ("unknown_column", "warning"): "Columns the game does not use",
                             ("duplicate_column", "error"): "Duplicate columns",
                             ("duplicate_column", "warning"): "Duplicate columns"}
            for (code, sev), items in groups.items():
                first = items[0]
                icon = "🛑" if sev == "error" else "⚠️" if sev == "warning" else "ℹ️"
                if (code, sev) in column_titles:
                    title = f"{column_titles[(code, sev)]}: " + ", ".join(i.column or "?" for i in items)
                else:
                    lines = ", ".join(str(i.line_no) for i in items[:12] if i.line_no)
                    title = code.replace("_", " ").capitalize() + (f" — {len(items)}×" if len(items) > 1 else "") + (
                        f" (line{'s' if len(items) > 1 else ''} {lines}{' …' if len(items) > 12 else ''})"
                        if lines else "")
                with st.expander(f"{icon} {title}"):
                    per_item = first.code in ("missing_column", "unknown_column")
                    if not per_item:
                        st.markdown(f"**What to do:** {hint(first, result.parsed.header)}")
                    st.dataframe(pd.DataFrame([{"line": i.line_no, "id": i.ext_id, "column": i.column,
                                                "problem": i.message,
                                                **({"what to do": hint(i, result.parsed.header)} if per_item else {})}
                                               for i in items]),
                                 width="stretch", hide_index=True)
        if missing_required:
            st.error("A required column is missing, so the file cannot be imported. Fix the header line and "
                     "upload it again.")
        elif st.button(f"Import into '{name}'", type="primary"):
            with db.session() as s:
                res = ds_service.import_dataset(s, data, dataset_name=name, source_filename=up.name,
                                                profile_name=profile)
            if not res.created:
                st.info(f"This file is identical to version {res.version_no} — nothing new to import.")
            else:
                msg = f"Imported as version {res.version_no} of **{name}**."
                if res.diff is not None:
                    d = res.diff
                    msg += (f" Since the previous version: {len(d.added)} added, {len(d.changed)} changed, "
                            f"{len(d.removed)} removed — only new and changed questions need checking.")
                st.success(msg)
            st.button("Next: 2 · Validate", on_click=go, args=("2 · Validate", name), type="primary")

# ===========================================================================================
elif page == "2 · Validate":
    name = need_dataset()
    st.title("2 · Validate")
    states = workflow.question_states(db, name)

    @st.fragment(run_every=5)
    def progress_box() -> None:
        """Live status of the running batch (refreshes every few seconds)."""
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

    c = workflow.counts(states)
    checkable = len(states) - c["format_error"]
    done = checkable - c["not_checked"] - c["failed"] - c["in_progress"]
    st.progress(done / max(checkable, 1), text=f"{done} of {checkable} questions checked"
                + (f" ({c['format_error']} with format errors are skipped)" if c["format_error"] else ""))
    progress_box()
    running = worker.status(settings.data_dir).running

    tab_go, tab_list = st.tabs(["Next batch", "Priority list"])
    cats = sorted({s.category for s in states if s.category})
    with tab_go:
        with st.expander("Choose which questions (optional)", expanded=False):
            sel_cats = st.multiselect("Categories", cats)
            subs = sorted({s.subcategory for s in states if s.subcategory
                           and (not sel_cats or s.category in sel_cats)})
            sel_subs = st.multiselect("Subcategories", subs)
            sel_levels = st.multiselect("Priority", ["high", "medium", "low"],
                                        help="A quick guess from the wording — see the Priority list tab")
            order = st.radio("Order", ["priority", "file"], horizontal=True,
                             format_func=lambda o: "Highest priority first" if o == "priority" else "As in the file")
        sel = workflow.Selection(categories=tuple(sel_cats), subcategories=tuple(sel_subs),
                                 levels=tuple(sel_levels), order=order)
        default = load_research_config().batch_size
        today = workflow.suggested_batch_size(db, default)
        size = st.number_input("Questions in this batch", min_value=1, max_value=200, value=max(today, 1),
                               help=f"Suggested from today's free limits (at most {default}). A batch stops "
                                    "by itself when a free limit is reached.")
        plan = workflow.plan_next_batch(db, name, sel, int(size))
        if today == 0 and plan.action == "start":
            st.warning(f"Today's free AI requests are used up. They come back at "
                       f"**{workflow.next_reset_local():%H:%M} ({workflow.next_reset_local():%A})**.")
        st.markdown(plan.message)
        if plan.questions:
            st.dataframe(pd.DataFrame([{"id": q.ext_id, "priority": q.priority_level, "why first": ", ".join(
                q.priority_reasons), "question": q.question, "category": q.category} for q in plan.questions]),
                width="stretch", hide_index=True, height=min(38 * (len(plan.questions) + 1), 300))
        label = "Continue the stopped batch" if plan.action == "resume" else "Validate next batch"
        if running:
            st.button(label, disabled=True, help="A batch is already running")
        elif today == 0 and plan.action != "nothing":
            st.button(label, disabled=True, help="Today's free AI requests are used up")
        elif plan.action != "nothing" and st.button(label, type="primary"):
            args = ["--size", str(int(size)), "--order", sel.order]
            for flag, values in (("--category", sel.categories), ("--subcategory", sel.subcategories),
                                 ("--priority", sel.levels)):
                for v in values:
                    args += [flag, v]
            worker.start_background(settings.data_dir, name, args)
            st.rerun()
        st.caption("Terminal: `qv next " + name + "` does the same. Run it again whenever it stops.")
    with tab_list:
        st.caption("Questions not checked yet, most error-prone first (a quick guess from the wording, no AI).")
        rows = [{"id": s.ext_id, "priority": s.priority_level, "points": s.priority_score,
                 "why": ", ".join(s.priority_reasons), "status": s.label, "question": s.question,
                 "category": s.category, "subcategory": s.subcategory}
                for s in sorted(states, key=lambda s: (-s.priority_score, s.row_no)) if s.status in workflow.CHECKABLE]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        if c["format_error"]:
            st.warning(f"{c['format_error']} question(s) have format errors and are skipped — fix them in the file "
                       "and import it again.")

# ===========================================================================================
elif page == "3 · Review":
    name = need_dataset()
    st.title("3 · Review")
    states = workflow.question_states(db, name)
    edits = workflow.pending_edits(states)
    if edits:
        st.info(f"✎ You edited {len(edits)} question(s). They can be exported as they are, or checked again with "
                "the new wording first (they then go to the front of the next batch).")
        if st.button("Check my edits again"):
            v = workflow.apply_edits_as_new_version(db, name)
            st.success(f"Saved as version {v}. Validate the next batch to check the edited questions.")
            st.rerun()
    groups = {k: [s for s in states if s.status == k] for k in workflow.REVIEW_STATUSES}
    groups["decided"] = [s for s in states if s.status in ("approved", "edited", "removed")
                         or (s.status == "specialist" and s.decision == "specialist")]
    labels = {k: f"{STATUS_LABEL.get(k, 'Decided')} ({len(v)})" for k, v in groups.items()}
    labels["decided"] = f"Decided ({len(groups['decided'])})"
    first = next((k for k in workflow.REVIEW_STATUSES if groups[k]), "to_review")
    group = st.segmented_control("Group", list(labels), format_func=labels.get, default=first,
                                 label_visibility="collapsed", key=f"group_{name}") or first
    st.caption(GROUP_HELP[group])
    items = sorted(groups[group], key=lambda s: (s.later, -s.priority_score, s.row_no))
    if group == "specialist" and items:
        from qv.services.exports import results_csv
        st.download_button("⬇ Download the list for your specialist (CSV)", results_csv(db, items),
                           file_name=f"{name}-for-specialist.csv", mime="text/csv")
    if not items:
        st.success("Nothing here. 🎉")
        if any(groups[k] for k in workflow.REVIEW_STATUSES):
            st.caption("Pick another group above.")
        else:
            next_step_card(name)
        st.stop()
    pos_key = f"pos_{name}_{group}"
    pos = min(st.session_state.get(pos_key, 0), len(items) - 1)
    options = list(range(len(items)))
    pos = st.selectbox("Question", options, index=pos, format_func=lambda i: (
        f"#{items[i].ext_id} — {items[i].question[:100]}" + ("  (later)" if items[i].later else "")))
    st.session_state[pos_key] = pos
    item = items[pos]

    nav = st.columns([1, 1, 6])
    if nav[0].button("◀ Previous", disabled=pos == 0):
        st.session_state[pos_key] = pos - 1
        st.rerun()
    if nav[1].button("Next ▶", disabled=pos >= len(items) - 1):
        st.session_state[pos_key] = pos + 1
        st.rerun()

    st.subheader(f"#{item.ext_id} {item.question}")
    if item.type == "multi":
        key_idx = int(item.answer) - 1 if item.answer.isdigit() else -1
        st.markdown("  ·  ".join(("✅ " if i == key_idx else "") + f"**{'ABCD'[i]}.** {o}"
                                 for i, o in enumerate(item.options) if o))
    else:
        st.markdown(f"**Answer:** {item.answer_text}")
    if item.note:
        st.markdown(f"**Note:** {item.note}")
    st.caption(" > ".join(x for x in (item.category, item.subcategory, item.topic) if x)
               + f" · {item.difficulty} · priority {item.priority_level}")

    v = views.question_verdict(db, item.run_id, item.ext_id) if item.run_id else None
    if v:
        box = {"VERIFIED": st.success, "INCORRECT": st.error, "OUTDATED": st.error}.get(v["verdict"], st.warning)
        box(f"**{v['verdict']}** — {VERDICT_TEXT[v['verdict']]}"
            + (f" Problem is in the **{v['defect_location'].replace('_', ' ')}**." if v["defect_location"] else ""))
        st.markdown(f"**{v['evidence_summary']}**")
        if v["blind_status"]:
            same = {True: " (same as the answer)", False: " (**different** from the answer)", None: ""}[
                v["blind_matches_key"]]
            st.markdown(f"Read **without** knowing the answer, the sources say: "
                        f"*{v['blind_answer'] or v['blind_status'].replace('_', ' ')}*{same}")
        if v["suggested_answer"]:
            st.markdown(f"💡 Suggested answer: **{v['suggested_answer']}**")
        if v["suggested_question"]:
            st.markdown(f"💡 Suggested question: **{v['suggested_question']}**")
        with st.expander("Why, and the sources"):
            st.markdown("\n".join(f"- {r}" for r in v["reasons_json"]))
            detail = views.question_detail(db, item.run_id, v["question_id"])
            for d in detail["documents"]:
                for p in d["passages"][:3]:
                    st.markdown(f"> {p['quote']}")
                    st.caption(f"{p['short_id']} · [{d['title'] or d['url']}]({d['url']}) · "
                               f"{TIER_LABEL.get(d['effective_tier'] or d['registry_tier'], '?')}")
            st.caption("Everything about this question: Advanced → Question details, run "
                       f"{item.run_id}.")
    if item.decision:
        hist = workflow.decision_history(db, name, item.ext_id)
        st.caption("Your decisions: " + " · ".join(f"{h['when']} {h['action']}"
                                                   + (f" ({h['comment']})" if h["comment"] else "") for h in hist))

    st.markdown("#### Your decision")
    comment = st.text_input("Comment (optional)", key=f"comment_{item.ext_id}")
    b = st.columns(5)

    def decide(action: str, changes: dict | None = None) -> None:
        """Store a decision and stay on the same position (the next question moves up)."""
        workflow.record_decision(db, name, item.ext_id, action, changes=changes, comment=comment)
        st.toast(f"#{item.ext_id}: {action}")

    if b[0].button("✔ Keep as is", help="You checked it: it is right", width="stretch"):
        decide("keep")
        st.rerun()
    if b[1].button("✎ Edit", width="stretch"):
        st.session_state[f"editing_{item.ext_id}"] = True
    if b[2].button("🎓 Ask the specialist", width="stretch"):
        decide("specialist")
        st.rerun()
    if b[3].button("✖ Remove", help="Leave it out of the export", width="stretch"):
        decide("remove")
        st.rerun()
    if b[4].button("⏭ Later", width="stretch"):
        decide("later")
        st.session_state[pos_key] = pos + 1
        st.rerun()

    if st.session_state.get(f"editing_{item.ext_id}"):
        sugg_q = (v or {}).get("suggested_question") or ""
        sugg_a = (v or {}).get("suggested_answer") or ""
        use = st.checkbox("Start from the suggestion", value=bool(sugg_q or sugg_a),
                          disabled=not (sugg_q or sugg_a))
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
                    decide("edit", new)
                    st.session_state[f"editing_{item.ext_id}"] = False
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

# ===========================================================================================
elif page == "4 · Export":
    from qv.services.exports import ExportError, workflow_export
    name = need_dataset()
    st.title("4 · Export")
    states = workflow.question_states(db, name)
    c = workflow.counts(states)
    st.markdown(f"**{len(states)}** questions · verified **{c['verified']}** · checked by you **{c['approved']}** "
                f"· edited **{c['edited']}** · removed **{c['removed']}** · still open "
                f"**{sum(c[k] for k in workflow.REVIEW_STATUSES) + c['not_checked'] + c['failed']}**")
    if sum(c[k] for k in workflow.REVIEW_STATUSES) + c["not_checked"]:
        st.info("You can export at any time; questions not checked or not reviewed yet are exported unchanged in "
                "the corrected file and left out of the verified-only file.")
    downloads = [
        ("corrected", "⬇ Corrected file", "The whole file with your edits applied and removed questions left out. "
                                         "Same ids, same order, format checked again."),
        ("verified", "⬇ Verified only", "Only questions that were verified or that you kept or edited."),
        ("results", "⬇ Results report", "One line per question: result, your decision, suggestions, reasons and "
                                       "sources (opens in Excel / Numbers)."),
    ]
    for kind, label, text in downloads:
        cols = st.columns([2, 5])
        try:
            data, fname, summary = workflow_export(db, name, kind)
            cols[0].download_button(label, data, file_name=fname, mime="text/csv", width="stretch",
                                    type="primary" if kind == "corrected" else "secondary")
            cols[1].markdown(text + "  \n" + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in summary.items()))
        except ExportError as exc:
            cols[0].button(label, disabled=True)
            cols[1].error(f"Cannot build this file: {exc}")
    st.markdown("#### Then, in the game")
    st.markdown("Copy the corrected file to `game_editions/<edition>/questions.csv`, then run "
                "`npm run build:content` and play a round. The validator never writes into the game's folders "
                "itself. When you change questions in the game later, import the file again: only new and "
                "changed questions are checked.")

# ===========================================================================================
else:
    st.title("Advanced")
    st.caption("Detailed views for checking how the validator works. Everything here also exists as a `qv` "
               "command; the database itself is described in DATABASE.md.")
    tab_q, tab_f, tab_r, tab_u = st.tabs(["Question details", "Files & format", "Batches (runs)", "Usage & quota"])

    with tab_f:
        overview = views.datasets_overview(db)
        if overview:
            st.dataframe(table(overview, ("version_id",)), width="stretch", hide_index=True)
            labels_v = {f"{o['dataset']} v{o['version']} ({o['file']})": o["version_id"] for o in overview}
            vid = labels_v[st.selectbox("Version", list(labels_v))]
            t1, t2 = st.tabs(["Questions", "Format problems"])
            with t1:
                rows = views.version_questions(db, vid)
                text = st.text_input("Filter (text in question, key or category)")
                if text:
                    t = text.lower()
                    rows = [r for r in rows if t in r["question"].lower() or t in r["key"].lower()
                            or t in r["category"].lower()]
                st.caption(f"{len(rows)} questions")
                st.dataframe(table(rows), width="stretch", hide_index=True)
            with t2:
                issues = views.version_issues(db, vid)
                sev = st.multiselect("Severity", ["error", "warning", "info"], default=["error", "warning"])
                st.dataframe(table([i for i in issues if i["severity"] in sev]), width="stretch", hide_index=True)

    with tab_r:
        st.dataframe(table(views.runs_overview(db)), width="stretch", hide_index=True)

    with tab_u:
        st.markdown("**Free quota left now**")
        st.dataframe(pd.DataFrame(views.quota_rows(db)), width="stretch", hide_index=True)
        st.caption(f"Gemini's daily limits come back at {workflow.next_reset_local():%H:%M} local time.")
        st.markdown("**Calls so far** (free tiers only: cost is always $0)")
        st.dataframe(table(views.usage_summary(db)), width="stretch", hide_index=True)

    with tab_q:
        runs = views.runs_overview(db)
        if not runs:
            st.info("Nothing checked yet.")
        else:
            with st.expander("What the words mean"):
                st.markdown(LEGEND)
            order_runs = sorted(runs, key=lambda r: (r["dataset"] != dataset, -r["run"]))  # this file's first
            run_id = st.selectbox("Batch (run)", [r["run"] for r in order_runs],
                                  format_func=lambda r: next(f"run {x['run']} · {x['dataset']} · {x['created']}"
                                                             for x in runs if x["run"] == r))
            qs = views.run_questions(db, run_id)
            if qs:
                st.dataframe(table(qs), width="stretch", hide_index=True)
                labels_q = {f"#{q['id']} — {q['verdict']} — {q['question'][:90]}": q["_qid"] for q in qs}
                qid = labels_q[st.selectbox("Question", list(labels_q))]
                detail = views.question_detail(db, run_id, qid)
                q = detail["question"]
                st.subheader(f"#{q['id']} {q['question']}")
                if q["type"] == "multi":
                    st.markdown("  ·  ".join(f"**{'ABCD'[i]}.** {o}" for i, o in enumerate(q["options"]) if o))
                st.markdown(f"**Expected answer:** {q['key']}" + (f"  ·  **Note:** {q['note']}" if q["note"] else ""))
                v = views.question_verdict(db, run_id, q["id"])
                if v is None:
                    st.info(f"Not judged in this run (`qv judge {run_id}` gives a verdict).")
                else:
                    st.code("\n".join(v["summary_lines"]), language=None)
                st.markdown("#### Evidence")
                st.caption("Every passage was found word for word in the stored copy of the page.")
                for d in detail["documents"]:
                    badge = TIER_LABEL.get(d["effective_tier"] or d["registry_tier"], "?")
                    purpose = "for the question" if d["mode"] == "A" else "for the note"
                    with st.expander(f"{d['title'] or d['url']} — {badge}"
                                     f"{' · frame authority' if d['frame_authority'] else ''} · {purpose} · "
                                     f"{d['grounded']} passage(s)", expanded=False):
                        st.markdown(f"[{d['url']}]({d['url']}) · read {d['fetched']} · {d['page_kind'] or '-'} · "
                                    f"{STATUS_TEXT.get(d['status'], d['status'])}"
                                    + (f" · {d['dropped']} quote(s) rejected" if d["dropped"] else ""))
                        if d["concerns"]:
                            st.warning("Concerns: " + "; ".join(d["concerns"]))
                        for p in d["passages"]:
                            st.markdown(f"> {p['quote']}")
                            meta = [f"about {p['target']}"]
                            if p["asserted_answer"]:
                                meta.append(f"says: {p['asserted_answer']}")
                            st.caption(f"{p['short_id']}" + (f" · origin {p['cluster']}" if p["cluster"] else "")
                                       + " · " + " · ".join(meta))
                        if d["passages"] and st.checkbox("Show in context", key=f"ctx{d['doc_id']}{d['mode']}"):
                            st.markdown(highlight(d["text"], d["passages"]), unsafe_allow_html=True)
                with st.expander("How the research was planned (S1a / S1b)"):
                    st.json({k: v["output"] for k, v in detail["stages"].items() if k in ("s1a", "s1b")})
                with st.expander("Research statistics"):
                    st.json(detail["stats"])
