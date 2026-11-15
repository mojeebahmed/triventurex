"""Read-only web view (Streamlit). Run with `qv ui`.

Thin by design: every query is in qv.services.views. Nothing here writes to the
database, calls a model or spends quota — long work runs from the CLI.
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from qv.config import Settings
from qv.db.session import Database
from qv.services import views

st.set_page_config(page_title="Question Validator", layout="wide")

TIER_LABEL = {"P": "P · primary", "S": "S · secondary", "T": "T · tertiary", "X": "X · excluded"}


@st.cache_resource
def get_db() -> Database:
    """One database handle per server process."""
    return Database(Settings().database_url)


def table(rows: list[dict], hide: tuple[str, ...] = ("_qid",)) -> pd.DataFrame:
    """DataFrame without internal columns."""
    df = pd.DataFrame(rows)
    return df.drop(columns=[c for c in hide if c in df.columns]) if not df.empty else df


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
page = st.radio("View", ["Datasets", "Research", "Usage"], horizontal=True, label_visibility="collapsed")

if page == "Datasets":
    st.title("Datasets")
    overview = views.datasets_overview(db)
    if not overview:
        st.info("Nothing imported yet: `qv import <file.csv> --dataset <name>`")
        st.stop()
    st.dataframe(table(overview, ("version_id",)), use_container_width=True, hide_index=True)
    labels = {f"{o['dataset']} v{o['version']}": o["version_id"] for o in overview}
    choice = st.selectbox("Version", list(labels))
    vid = labels[choice]
    tab_q, tab_i = st.tabs(["Questions", "Structural issues"])
    with tab_q:
        rows = views.version_questions(db, vid)
        text = st.text_input("Filter (text in question, key or category)")
        if text:
            t = text.lower()
            rows = [r for r in rows if t in r["question"].lower() or t in r["key"].lower()
                    or t in r["category"].lower()]
        st.caption(f"{len(rows)} questions")
        st.dataframe(table(rows), use_container_width=True, hide_index=True)
    with tab_i:
        issues = views.version_issues(db, vid)
        sev = st.multiselect("Severity", ["error", "warning", "info"], default=["error", "warning"])
        st.dataframe(table([i for i in issues if i["severity"] in sev]), use_container_width=True, hide_index=True)

elif page == "Research":
    st.title("Research runs")
    runs = views.runs_overview(db)
    if not runs:
        st.info("No research yet: `qv research <dataset> --ids 1,2,3`")
        st.stop()
    st.dataframe(table(runs), use_container_width=True, hide_index=True)
    run_id = st.selectbox("Run", [r["run"] for r in runs])
    qs = views.run_questions(db, run_id)
    st.dataframe(table(qs), use_container_width=True, hide_index=True)
    if not qs:
        st.stop()
    labels = {f"#{q['id']} — {q['question'][:90]}": q["_qid"] for q in qs}
    detail = views.question_detail(db, run_id, labels[st.selectbox("Question", list(labels))])
    q = detail["question"]

    st.subheader(f"#{q['id']} {q['question']}")
    cols = st.columns(3)
    cols[0].markdown(f"**Key:** {q['key']}")
    cols[1].markdown(f"**Category:** {q['category']}")
    cols[2].markdown(f"**Status:** {detail['status']}")
    if q["type"] == "multi":
        st.markdown("  ·  ".join(f"**{'ABCD'[i]}.** {o}" for i, o in enumerate(q["options"]) if o))
    if q["note"]:
        st.markdown(f"**Note:** {q['note']}")

    s1a = detail["stages"].get("s1a")
    s1b = detail["stages"].get("s1b")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### S1a · answer-blind decomposition")
        if s1a:
            o = s1a["output"]
            st.markdown(f"*{s1a['model']}* — **need:** {o['information_need']}")
            st.markdown(f"claim type `{o['claim_type']}` · frame `{o['frame_class']}` · answer `{o['answer_type']}`")
            for p in o["presuppositions"]:
                st.markdown(f"- **{p['id']}** {p['text']}{'' if p['material'] else ' *(not material)*'}")
            st.markdown("**Blind queries**")
            for x in o["queries"]:
                st.markdown(f"- `{x['purpose']}` {x['q']}")
            for c in s1a["checks"]:
                st.warning(c)
    with c2:
        st.markdown("#### S1b · claims (sees the key)")
        if s1b:
            o = s1b["output"]
            st.markdown(f"*{s1b['model']}* — **key claim:** {o['key_claim']}")
            for k in o["key_components"]:
                st.markdown(f"- **{k['id']}** {k['text']}")
            if o["answer_equivalents"]:
                st.markdown("**Equivalents:** " + ", ".join(o["answer_equivalents"]))
            for n in o["note_claims"]:
                st.markdown(f"- **{n['id']}** `{n['kind']}` {n['text']}")
            st.markdown("**Challenge queries**")
            for c in o["challenge_queries"]:
                st.markdown(f"- `{c['angle']}` {c['q']}")

    st.markdown("#### Documents and grounded passages")
    st.caption("Every passage below was found verbatim in the stored copy of the page (grounding check). "
               "Mode A = read without the key; mode B = read for the note's claims.")
    for d in detail["documents"]:
        badge = TIER_LABEL.get(d["effective_tier"] or d["registry_tier"], "?")
        title = d["title"] or d["url"]
        header = (f"[{d['mode']}] {title} — {badge}{' · frame authority' if d['frame_authority'] else ''} · "
                  f"{d['page_kind'] or '-'} · {d['grounded']} passages")
        with st.expander(header, expanded=d["grounded"] > 0):
            st.markdown(f"[{d['url']}]({d['url']}) · fetched {d['fetched']} · status `{d['status']}`"
                        + (f" · {d['dropped']} quote(s) dropped by the grounding check" if d["dropped"] else ""))
            if d["concerns"]:
                st.warning("Concerns: " + "; ".join(d["concerns"]))
            if d["about_right_subject"] is False:
                st.error("The reader judged this page to be about a different subject; its passages are not used.")
            via = sorted({f"{f.get('via')}: {f.get('query') or f.get('ref')}" for f in d["found_by"]})
            st.caption("Found by: " + " | ".join(via))
            for p in d["passages"]:
                meta = [f"target **{p['target']}**"]
                if p["asserted_answer"]:
                    meta.append(f"says the answer is **{p['asserted_answer']}**"
                                + (f" (option {p['matches_option']})" if p["matches_option"] else ""))
                if p["stance"]:
                    meta.append(f"stance **{p['stance']}**")
                for k, label in (("qualifiers", "qualifiers"), ("as_of", "as of"), ("origin", "origin")):
                    if p[k]:
                        meta.append(f"{label}: {p[k]}")
                if p["primary"]:
                    meta.append("primary source")
                st.markdown(f"> {p['quote']}")
                st.caption(f"P{p['pid']} · " + " · ".join(meta))
            if d["passages"] and st.checkbox("Show passages in context", key=f"ctx{d['doc_id']}{d['mode']}"):
                st.markdown(highlight(d["text"], d["passages"]), unsafe_allow_html=True)
    with st.expander("Research statistics"):
        st.json(detail["stats"])

else:
    st.title("API usage")
    st.caption("Free tiers only: cost is always $0. Credits = requests (Gemini, Parallel), "
               "credits (Tavily) or USD of free credit (Exa).")
    st.dataframe(table(views.usage_summary(db)), use_container_width=True, hide_index=True)
