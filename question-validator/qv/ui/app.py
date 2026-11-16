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
LEGEND = """
**Verdicts** — VERIFIED · INCORRECT · OUTDATED · CONTESTED · AMBIGUOUS · UNVERIFIED (not enough evidence; not
the same as wrong). Only VERIFIED needs no look.

**Evidence for the answer** — STRONG: meets the bar for this kind of fact (e.g. the verse itself for a Qur'an
question; the official record or two independent expert sources for a record) · MODERATE: some independent
support, below the bar · WEAK: one source · NONE.

**Answer found without the key** — the evidence was read by a step that was *not told* the expected answer.
"same" is the strongest sign the answer is right; "different" is the strongest sign of an error.

**Sources** — P primary (the text itself, the official record, the author's own book) · S expert (scholarly,
reputable news, official histories) · T encyclopaedia / summary · X not evidence (quiz sites, forums). A
*frame authority* is an official source of the edition's tradition (e.g. alislam.org).

**Origins (C1, C2 …)** — passages that trace back to the same source count once, however many sites repeat it.

**Next step** — auto ok: nothing to do · audit sample: a random check of auto-ok questions · needs review: look at
it · needs specialist: a religious question for the edition's reviewer · needs evidence: try more sources.
"""


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
page = st.radio("View", ["Questions", "Datasets", "Usage"], horizontal=True, label_visibility="collapsed")

if page == "Datasets":
    st.title("Datasets")
    overview = views.datasets_overview(db)
    if not overview:
        st.info("Nothing imported yet: `qv import <file.csv> --dataset <name>`")
        st.stop()
    st.dataframe(table(overview, ("version_id",)), width="stretch", hide_index=True)
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
        st.dataframe(table(rows), width="stretch", hide_index=True)
    with tab_i:
        issues = views.version_issues(db, vid)
        sev = st.multiselect("Severity", ["error", "warning", "info"], default=["error", "warning"])
        st.dataframe(table([i for i in issues if i["severity"] in sev]), width="stretch", hide_index=True)

elif page == "Questions":
    st.title("Questions")
    runs = views.runs_overview(db)
    if not runs:
        st.info("Nothing checked yet: `qv validate <dataset> --ids 1,2,3` (or `qv research`, then `qv judge <run>`)")
        st.stop()
    with st.expander("What the words on this page mean"):
        st.markdown(LEGEND)
    with st.expander("Runs"):
        st.dataframe(table(runs), width="stretch", hide_index=True)
    run_id = st.selectbox("Run", sorted((r["run"] for r in runs), reverse=True))
    qs = views.run_questions(db, run_id)
    if not qs:
        st.stop()
    st.dataframe(table(qs), width="stretch", hide_index=True)
    labels = {f"#{q['id']} — {q['verdict']} — {q['question'][:90]}": q["_qid"] for q in qs}
    qid = labels[st.selectbox("Question", list(labels))]
    detail = views.question_detail(db, run_id, qid)
    q = detail["question"]

    st.subheader(f"#{q['id']} {q['question']}")
    if q["type"] == "multi":
        st.markdown("  ·  ".join(f"**{'ABCD'[i]}.** {o}" for i, o in enumerate(q["options"]) if o))
    st.markdown(f"**Expected answer:** {q['key']}" + (f"  ·  **Note:** {q['note']}" if q["note"] else ""))
    st.caption(q["category"])

    # --- the summary: verdict first, in plain words
    v = views.question_verdict(db, run_id, q["id"])
    if v is None:
        st.info(f"Not judged yet — run `qv judge {run_id}` to get a verdict.")
    else:
        box = {"VERIFIED": st.success, "INCORRECT": st.error, "OUTDATED": st.error}.get(v["verdict"], st.warning)
        box(f"**{v['verdict']}** — {VERDICT_TEXT[v['verdict']]}"
            + (f" Problem is in the **{v['defect_location'].replace('_', ' ')}**." if v["defect_location"] else ""))
        c = st.columns(4)
        c[0].metric("Evidence for the answer", v["evidence_strength"])
        c[1].metric("Answer found without the key",
                    {True: "same", False: "different", None: "—"}[v["blind_matches_key"]])
        c[2].metric("Question quality", v["question_quality"] or "—")
        c[3].metric("Next step", v["review_status"].replace("_", " "))
        st.markdown(f"**{v['evidence_summary']}**")
        if v["blind_status"]:
            st.markdown(f"Read **without** knowing the expected answer, the evidence gives: "
                        f"**{v['blind_answer'] or v['blind_status'].replace('_', ' ')}**")
        if v["suggested_answer"]:
            st.markdown(f"Suggested answer: **{v['suggested_answer']}**")
        if v["suggested_question"]:
            st.markdown(f"Suggested question: **{v['suggested_question']}**")
        if v["note_status"]:
            st.markdown(f"Note: **{v['note_status'].replace('_', ' ')}**")
        st.markdown("**Why**\n" + "\n".join(f"- {r}" for r in v["reasons_json"]))
        issues = (v["quality_json"] or {}).get("issues", [])
        if issues:
            with st.expander(f"Quality issues ({len(issues)})"):
                for i in issues:
                    st.markdown(f"- **{i['type'].replace('_', ' ')}** ({i['severity']}"
                                + (", a guess to check" if i["is_hypothesis"] else "") + f"): {i['detail']}")
                rw = (v["quality_json"] or {}).get("suggested_rewrite")
                if rw:
                    st.markdown(f"Suggested rewrite: *{rw['question']}* → {rw['answer']}")

    # --- evidence
    st.markdown("#### Evidence")
    st.caption("Every passage was found word for word in the stored copy of the page. P-numbers match the "
               "reasons above; passages with the same origin letter (C1, C2 …) count as one source.")
    for d in detail["documents"]:
        badge = TIER_LABEL.get(d["effective_tier"] or d["registry_tier"], "?")
        title = d["title"] or d["url"]
        purpose = "for the question" if d["mode"] == "A" else "for the note"
        header = (f"{title} — {badge}{' · frame authority' if d['frame_authority'] else ''} · "
                  f"{purpose} · {d['grounded']} passage{'s' if d['grounded'] != 1 else ''}")
        with st.expander(header, expanded=d["grounded"] > 0):
            st.markdown(f"[{d['url']}]({d['url']}) · read {d['fetched']} · {d['page_kind'] or '-'} · "
                        f"{STATUS_TEXT.get(d['status'], d['status'])}"
                        + (f" · {d['dropped']} quote(s) rejected (not found word for word)" if d["dropped"] else ""))
            if d["concerns"]:
                st.warning("Concerns: " + "; ".join(d["concerns"]))
            if d["about_right_subject"] is False:
                st.error("This page is about a different subject; its passages are not used.")
            for p in d["passages"]:
                meta = [f"about **{p['target']}**"]
                if p["asserted_answer"]:
                    meta.append(f"says the answer is **{p['asserted_answer']}**"
                                + (f" (option {p['matches_option']})" if p["matches_option"] else ""))
                if p["stance"]:
                    meta.append(f"{p['stance']}")
                for k, label in (("qualifiers", "only if"), ("as_of", "as of"), ("origin", "credits")):
                    if p[k]:
                        meta.append(f"{label}: {p[k]}")
                st.markdown(f"> {p['quote']}")
                st.caption(f"{p['short_id']}" + (f" · origin {p['cluster']}" if p["cluster"] else "")
                           + " · " + " · ".join(meta))
            if d["passages"] and st.checkbox("Show passages in context", key=f"ctx{d['doc_id']}{d['mode']}"):
                st.markdown(highlight(d["text"], d["passages"]), unsafe_allow_html=True)
            via = sorted({f"{f.get('via')}: {f.get('query') or f.get('ref')}" for f in d["found_by"]})
            st.caption("Found by: " + " | ".join(via))

    # --- how the research was planned (details)
    s1a = detail["stages"].get("s1a")
    s1b = detail["stages"].get("s1b")
    with st.expander("How the research was planned (S1a / S1b)"):
        if s1a:
            o = s1a["output"]
            st.markdown(f"**Without the key** (*{s1a['model']}*): what needs to be known — {o['information_need']}")
            st.markdown(f"kind of fact `{o['claim_type']}` · frame `{o['frame_class']}`")
            for pr in o["presuppositions"]:
                st.markdown(f"- **{pr['id']}** (taken for granted) {pr['text']}"
                            + ("" if pr["material"] else " *(not essential)*"))
            st.markdown("Searches: " + " · ".join(f"`{x['q']}`" for x in o["queries"]))
            for c in s1a["checks"]:
                st.warning(c)
        if s1b:
            o = s1b["output"]
            st.markdown(f"**With the key** (*{s1b['model']}*): the claim being checked — {o['key_claim']}")
            if o["answer_equivalents"]:
                st.markdown("Also accepted: " + ", ".join(o["answer_equivalents"]))
            for n in o["note_claims"]:
                st.markdown(f"- **{n['id']}** (note) {n['text']}")
            st.markdown("Searches against the key: " + " · ".join(f"`{c['q']}`" for c in o["challenge_queries"]))
    with st.expander("Research statistics"):
        st.json(detail["stats"])

else:
    st.title("API usage")
    st.caption("Free tiers only: cost is always $0. Credits = requests (Gemini, Parallel), "
               "credits (Tavily) or USD of free credit (Exa).")
    st.dataframe(table(views.usage_summary(db)), width="stretch", hide_index=True)
