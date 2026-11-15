"""S0 — structural checks (no AI, no network).

Every check the game's own checker makes (scripts/content.js → checkEdition)
is reproduced with the same severity, so "no errors here" means
`npm run check:content` will not fail on questions.csv. Extra checks the game
does not make are added with their own codes.

Pure functions: ParsedCsv + rules → StructuralReport.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterator

from rapidfuzz import fuzz, process

from qv.config import StructuralRules
from qv.domain.question import (
    OPTION_COLUMNS, OPTION_LETTERS, REQUIRED_COLUMNS, LineEnding, ParsedCsv, Question,
)
from qv.domain.structural import IssueCode, Severity, StructuralIssue, StructuralReport
from qv.io.csv_format import js_trim

#: Near-duplicate detection compares this many questions per block (bounds memory).
_NEAR_DUP_BLOCK = 2000


def normalise_text(text: str) -> str:
    """Casefold, strip accents and punctuation, collapse whitespace — for comparing wording."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def run_structural_checks(parsed: ParsedCsv, rules: StructuralRules | None = None) -> StructuralReport:
    """Run every structural check on a parsed file and return the report."""
    rules = rules or StructuralRules()
    questions = [Question.from_row(r, parsed.header) for r in parsed.rows]
    issues: list[StructuralIssue] = []
    issues += _file_checks(parsed)
    if parsed.header and not any(c not in parsed.header for c in REQUIRED_COLUMNS):
        issues += _row_shape_checks(parsed)
        issues += _row_content_checks(questions, rules)
        issues += _duplicate_question_checks(questions, rules)
    elif parsed.header:
        # Without the required columns, row checks would only repeat the same problem.
        issues += _row_shape_checks(parsed)
    issues.sort(key=lambda i: (i.line_no or 0, list(Severity).index(i.severity), i.code))
    return StructuralReport(
        issues=tuple(issues),
        row_count=len(questions),
        multi_count=sum(1 for q in questions if q.type == "multi"),
        open_count=sum(1 for q in questions if q.type == "open"),
    )


def _file_checks(parsed: ParsedCsv) -> list[StructuralIssue]:
    """Encoding, BOM, line endings, header."""
    out: list[StructuralIssue] = []
    if parsed.decode_error:
        out.append(StructuralIssue(code=IssueCode.NOT_UTF8, severity=Severity.ERROR,
                                   message=f"File is {parsed.decode_error}; the game reads UTF-8"))
    if parsed.format.has_bom:
        out.append(StructuralIssue(code=IssueCode.BOM, severity=Severity.INFO,
                                   message="File starts with a UTF-8 byte-order mark (harmless; kept on export)"))
    if parsed.format.line_ending == LineEnding.MIXED:
        out.append(StructuralIssue(code=IssueCode.MIXED_LINE_ENDINGS, severity=Severity.INFO,
                                   message="File mixes line endings (kept as they are on export)"))
    if not parsed.header:
        out.append(StructuralIssue(code=IssueCode.EMPTY_FILE, severity=Severity.ERROR,
                                   message="No header row (first line is empty)", line_no=1))
        return out
    seen: set[str] = set()
    for col in parsed.header:
        if col in seen:
            out.append(StructuralIssue(code=IssueCode.DUPLICATE_COLUMN, severity=Severity.ERROR,
                                       message=f"Column '{col}' appears more than once", line_no=1, column=col))
        seen.add(col)
    for col in parsed.missing_columns:
        sev = Severity.ERROR if col in REQUIRED_COLUMNS else Severity.WARNING
        out.append(StructuralIssue(code=IssueCode.MISSING_COLUMN, severity=sev, line_no=1, column=col,
                                   message=f"Column '{col}' is missing"))
    for col in parsed.extra_columns:
        out.append(StructuralIssue(code=IssueCode.UNKNOWN_COLUMN, severity=Severity.INFO, line_no=1, column=col,
                                   message=f"Column '{col}' is not used by the game (kept on export)"))
    return out


def _row_shape_checks(parsed: ParsedCsv) -> list[StructuralIssue]:
    """Column counts, unbalanced quotes, whitespace the game trims."""
    out: list[StructuralIssue] = []
    width = len(parsed.header)
    for r in parsed.rows:
        ext_id = r.get("id") or None
        loc = {"row_no": r.row_no, "line_no": r.line_no, "ext_id": ext_id}
        if r.unbalanced_quotes:
            out.append(StructuralIssue(code=IssueCode.UNBALANCED_QUOTES, severity=Severity.ERROR, **loc,
                                       message='A double quote is opened but never closed — '
                                               'the rest of the line is read as one field'))
        if len(r.cells) != width:
            out.append(StructuralIssue(code=IssueCode.COLUMN_COUNT, severity=Severity.ERROR, **loc,
                                       message=f"{len(r.cells)} columns, expected {width} — "
                                               'a comma inside a field needs "double quotes"'))
        cols = [parsed.header[i] for i, c in enumerate(r.cells) if i < width and c != js_trim(c)]
        if cols:
            out.append(StructuralIssue(code=IssueCode.WHITESPACE, severity=Severity.INFO, **loc,
                                       column=cols[0],
                                       message=f"Leading/trailing spaces in {', '.join(cols)} "
                                               "(the game trims them)"))
    return out


def _row_content_checks(questions: list[Question], rules: StructuralRules) -> Iterator[StructuralIssue]:
    """Per-row rules: the game's checks plus option-level extras."""
    seen_ids: dict[str, int] = {}
    uses_topics = any(q.topic for q in questions)
    for q in questions:
        def issue(code: IssueCode, severity: Severity, message: str, column: str | None = None,
                  related: tuple[str, ...] = ()) -> StructuralIssue:
            return StructuralIssue(code=code, severity=severity, message=message, row_no=q.row_no,
                                   line_no=q.line_no, ext_id=q.ext_id or None, column=column,
                                   related_ext_ids=related)

        if not q.question:
            yield issue(IssueCode.EMPTY_QUESTION, Severity.ERROR, "Question text is empty", "question")
        if not re.fullmatch(r"\d+", q.ext_id):
            yield issue(IssueCode.INVALID_ID, Severity.ERROR, f'id "{q.ext_id}" must be a whole number', "id")
        elif q.ext_id in seen_ids:
            yield issue(IssueCode.DUPLICATE_ID, Severity.ERROR,
                        f"Duplicate id {q.ext_id} (also on line {seen_ids[q.ext_id]})", "id")
        else:
            seen_ids[q.ext_id] = q.line_no
        if q.type not in rules.allowed_types:
            yield issue(IssueCode.INVALID_TYPE, Severity.ERROR,
                        f'type "{q.type}" must be one of: {", ".join(rules.allowed_types)}', "type")
        if q.difficulty not in rules.allowed_difficulties:
            yield issue(IssueCode.INVALID_DIFFICULTY, Severity.ERROR,
                        f'difficulty "{q.difficulty}" must be one of: {", ".join(rules.allowed_difficulties)}',
                        "difficulty")
        if not q.category:
            yield issue(IssueCode.EMPTY_CATEGORY, Severity.INFO,
                        "No category (the game files it under 'general')", "category")
        if uses_topics and not q.topic:
            yield issue(IssueCode.NO_TOPIC, Severity.WARNING,
                        "No topic — the question is always asked, whatever the topic filter", "topic")

        if q.type == "multi":
            yield from _multi_checks(q, rules, issue)
        elif q.type == "open":
            if not q.answer:
                yield issue(IssueCode.OPEN_NO_ANSWER, Severity.ERROR, "Open question has no answer", "answer")
            if any(q.options):
                yield issue(IssueCode.OPEN_HAS_OPTIONS, Severity.WARNING,
                            "Open question has options filled in (the game ignores them)", "opt_a")


def _multi_checks(q: Question, rules: StructuralRules, issue) -> Iterator[StructuralIssue]:  # noqa: ANN001
    """Checks specific to multiple-choice rows."""
    filled = [i for i, o in enumerate(q.options) if o]
    if len(filled) < rules.min_multi_options:
        yield issue(IssueCode.MULTI_TOO_FEW_OPTIONS, Severity.ERROR,
                    f"Multi question needs at least {rules.min_multi_options} options", "opt_a")
    elif rules.warn_fewer_than_four_options and len(filled) < 4:
        yield issue(IssueCode.FEWER_THAN_FOUR_OPTIONS, Severity.INFO,
                    f"Only {len(filled)} options", OPTION_COLUMNS[len(filled)])

    idx = q.answer_index
    if not re.fullmatch(r"[1-4]", q.answer):
        yield issue(IssueCode.MULTI_ANSWER_NOT_INDEX, Severity.ERROR,
                    f'answer "{q.answer}" must be 1-4 (the option number)', "answer")
    elif idx is not None and not q.options[idx]:
        yield issue(IssueCode.MULTI_ANSWER_EMPTY_OPTION, Severity.ERROR,
                    f"answer {q.answer} points at an empty option", "answer")

    # An empty option before a filled one: the game drops it and later options move up a letter.
    if filled:
        gaps = [i for i in range(max(filled)) if not q.options[i]]
        if gaps:
            letters = ", ".join(OPTION_LETTERS[i] for i in gaps)
            if idx is not None and q.options[idx] and any(g < idx for g in gaps):
                # The game keeps the answer's letter but drops empty options, so the
                # letter now points `idx` places into the filled list.
                game_key = q.options[filled[idx]] if idx < len(filled) else "(no option)"
                yield issue(IssueCode.OPTION_GAP, Severity.ERROR,
                            f"Empty option {letters} before the answer: the game moves later options up, "
                            f"so it would mark \"{game_key}\" as correct instead of \"{q.options[idx]}\"",
                            OPTION_COLUMNS[gaps[0]])
            else:
                yield issue(IssueCode.OPTION_GAP, Severity.WARNING,
                            f"Empty option {letters} between filled options (the game moves later options up)",
                            OPTION_COLUMNS[gaps[0]])

    norm = defaultdict(list)
    for i in filled:
        norm[normalise_text(q.options[i])].append(OPTION_LETTERS[i])
    for letters in norm.values():
        if len(letters) > 1:
            yield issue(IssueCode.DUPLICATE_OPTIONS, Severity.WARNING,
                        f"Options {' and '.join(letters)} are the same", OPTION_COLUMNS[0])


def _duplicate_question_checks(questions: list[Question], rules: StructuralRules) -> list[StructuralIssue]:
    """Exact and near-duplicate question texts. Reported, never merged."""
    out: list[StructuralIssue] = []
    items = [(q, normalise_text(q.question)) for q in questions if q.question]
    groups: dict[str, list[Question]] = defaultdict(list)
    for q, n in items:
        groups[n].append(q)
    for group in groups.values():
        if len(group) < 2:
            continue
        ids = tuple(g.ext_id for g in group)
        for q in group[1:]:
            out.append(StructuralIssue(
                code=IssueCode.EXACT_DUPLICATE_QUESTION, severity=Severity.WARNING,
                row_no=q.row_no, line_no=q.line_no, ext_id=q.ext_id or None,
                related_ext_ids=tuple(i for i in ids if i != q.ext_id) or ids[:1],
                message=f"Same question text as id {group[0].ext_id} (line {group[0].line_no})",
            ))

    # Near duplicates: compare one representative per distinct normalised text.
    reps = [(g[0], n) for n, g in groups.items()]
    texts = [n for _, n in reps]
    threshold = rules.near_duplicate_threshold
    for start in range(0, len(texts), _NEAR_DUP_BLOCK):
        block = texts[start:start + _NEAR_DUP_BLOCK]
        scores = process.cdist(block, texts, scorer=fuzz.ratio, score_cutoff=threshold, workers=-1)
        for bi, row in enumerate(scores):
            i = start + bi
            for j in row.nonzero()[0]:
                if j <= i:
                    continue
                a, b = reps[i][0], reps[int(j)][0]
                # Similar wording with a different key is a template ("capital of X"), not a duplicate.
                key_a = normalise_text(a.resolved_answer_text or "")
                key_b = normalise_text(b.resolved_answer_text or "")
                if (fuzz.ratio(key_a, key_b) < rules.near_duplicate_answer_threshold
                        or re.findall(r"\d+", key_a) != re.findall(r"\d+", key_b)):
                    continue
                first, second = (a, b) if a.line_no < b.line_no else (b, a)
                out.append(StructuralIssue(
                    code=IssueCode.NEAR_DUPLICATE_QUESTION, severity=Severity.WARNING,
                    row_no=second.row_no, line_no=second.line_no, ext_id=second.ext_id or None,
                    related_ext_ids=(first.ext_id,),
                    message=f"Probably the same question as id {first.ext_id} (wording {row[j]:.0f}% "
                            "similar, same answer) — check; never merged automatically",
                ))
    return out
