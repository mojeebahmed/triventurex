# Factual Validation Methodology

*Version 1 — 2026-11-15. Design only; nothing is implemented yet.*
*This document defines **how** a question is judged. It refines §3 (workflow) and §3.4 (verdict rules) of
[ARCHITECTURE.md](ARCHITECTURE.md); where they differ, this document wins. The prompts and JSON schemas for
each stage are in [`prompts/`](prompts/).*

---

## 0. The failure mode this is designed against

> An AI searches for the expected answer, finds a website repeating it, and declares it correct.

That loop fails in four separate ways, and each needs its own countermeasure:

| Failure | Why it happens | Countermeasure (section) |
|---|---|---|
| **Confirmation search** — the query contains the answer, so results agree with it | The key is visible when queries are written | Queries are written by a stage that **never sees the key** (§3, S1) |
| **Echo sources** — quiz sites, fact lists and content farms repeat each other (and often the same error) | Every page counts as "a source" | Quiz/trivia/listicle pages are **excluded**; independence is counted by **origin of the fact**, not by website (§5) |
| **Agreement ≠ verification** — "a page says X" is accepted without checking whether the page is authoritative for *this kind* of claim | No notion of what evidence a claim needs | An **evidence requirement per claim type** (§4) — scripture needs the text, a record needs the record-keeper |
| **One model judges everything** — a confident first answer anchors every later stage | Stages see each other's conclusions | Evidence is read **blind**, an answer is formed **blind**, then compared; a second verifier is also blind; **code** decides the verdict (§3, §9) |

The single most important signal in this design: **does an answer formed from the evidence, without knowing
the key, agree with the key?** Everything else exists to make that signal trustworthy.

---

## 1. Principles

1. **Verdicts are about evidence, not truth.** "VERIFIED" means: positive, independent, authoritative-enough
   evidence supports the key, a blind reading of that evidence reaches the same answer, and nothing material
   contradicts it. It never means "the model believes it".
2. **Ask the question, don't test the answer.** Research is driven by the *information need* ("which player
   holds the record for most goals in one Premier League season, and how many?"), never by the key.
3. **Every option is a hypothesis.** For multiple choice, all four options are treated symmetrically during
   research and reading; the key gets no special status until verification.
4. **Questions contain claims too.** A question's presuppositions ("three *consecutive* World Cups") and its
   note ("Surah Al-Baqarah 2:32") are claims, tested like the answer.
5. **Only quoted, stored text counts.** A passage is evidence only if it is a verbatim substring of a document
   we fetched and stored. Models refer to passages by ID; they cannot introduce URLs, titles or quotes.
6. **Disagreement is classified before it is resolved.** A different number, a different definition, a
   different numbering scheme, a different theological position and a change over time are five different things.
7. **Frames are declared, not guessed.** An edition declares its frame of reference (e.g. Ahmadiyya
   understanding; Bismillah counted as verse 1). Claims inside the frame are judged against the frame's
   authorities; disagreement from outside it is recorded, not treated as error.
8. **Code decides; models describe.** Models produce structured findings (passages, stances, asserted answers,
   objections). A deterministic, versioned rules table turns those into the verdict.
9. **Uncertainty is a valid answer at every stage.** Each schema has an explicit "insufficient / unclear"
   value; prompts tell the model that using it is correct behaviour, not failure.

---

## 2. What gets judged: claims, not just questions

S1 decomposes every question into claims. Each claim gets its own evidence and its own status; the question
verdict is derived from the claim statuses (§9).

| Claim | Source | Example |
|---|---|---|
| **K — key claim** | question + resolved key | *"Erling Haaland scored 34 goals in the 2022–23 Premier League season, the most by one player in a season."* (Football Quest #66) |
| **PR — presupposition** | the question text | *"Brazil won three **consecutive** World Cups: 1958, 1962 and 1970."* (Football Quest #70) |
| **N — note claim** | the note column | *"Surah Al-Baqarah verse 32 (Bismillah = verse 1) says Allah taught Adam the names."* (Prophets' Stories #3) |
| **O — option claims** | MC options | *"Kenya is the country where Kilimanjaro is."* — investigated only when triggered (§7) |

The **information need** is the neutral form of the question used for research: what must be known to answer
it, without the answer. For #66: *"Which player has scored the most goals in a single Premier League season,
how many, in which season?"*

### Claim types

Each claim is classified, because the type decides what evidence is required (§4):

`scripture_content` · `hadith_or_tradition` · `attribution` (what a named person/body said or wrote) ·
`doctrine` (a belief of a tradition) · `historical_event` · `biography` · `measurement_or_superlative` ·
`statistic_current` · `sports_record` · `definition_or_meaning` · `classification_or_list` ·
`geography_fact` · `science_fact` · `other`

### Frame classes

| Frame class | Meaning | Example |
|---|---|---|
| `universal` | Any competent source should agree | Kilimanjaro is in Tanzania (World Tour #135) |
| `tradition_general` | About what a shared text/tradition says | The qibla was first towards Jerusalem (Prophets' Stories #170) |
| `attribution_to_frame` | About what a frame *teaches* — verifiable as a fact about the teaching | "According to the Promised Messiah (as), did Hadhrat Isa (as) die on the cross?" (#138) |
| `frame_specific` | A frame's belief stated **as fact** | "the tomb of Hadhrat Isa (as), known locally as the shrine of Yuz Asaf" (#140) |

The difference between the last two matters. #138 is phrased as attribution, so it is checkable like any
historical fact: what does *Jesus in India* say? Mainstream Christian or Sunni disagreement is irrelevant.
#140 states the belief as fact; its *universal* parts (a shrine called Roza Bal / Yuz Asaf exists in Srinagar)
are checked normally, and the frame-specific identification is judged against frame authorities and marked
**contested outside the frame**.

---

## 3. Stages and what each one may see

Information flow is the methodology. The key is hidden from every stage that gathers or reads evidence.

| Stage | Prompt | Sees question & options | Sees key | Sees note | Sees evidence | Sees other conclusions | Produces |
|---|---|---|---|---|---|---|---|
| **S1a Decomposition** | [s1a](prompts/s1a-question-decomposition.md) | ✔ (options unmarked) | ✘ | ✘ | ✘ | ✘ | information need, answer type, presuppositions, claim type, frame class, time sensitivity, conventions, interpretations, **blind queries** |
| **S1b Claim formulation** | [s1b](prompts/s1b-claim-formulation.md) | ✔ | ✔ | ✔ | ✘ | S1a | key claim, answer equivalents, note claims, direct lookups, **challenge queries** |
| S2 Retrieval | *(code)* | queries only | — | — | — | — | search results, fetched + stored documents, direct texts |
| **S3 Evidence extraction** | [s3](prompts/s3-evidence-extraction.md) | ✔ (options unmarked) | ✘ | ✘ (mode A) / note claims (mode B) | **one document** | ✘ | page assessment, verbatim passages, **what each passage says the answer is**, stance on presuppositions |
| *Grounding check* | *(code)* | | | | | | drops any passage not found verbatim |
| **S4 Blind answer** | [s4](prompts/s4-blind-answer.md) | ✔ (options unmarked) | ✘ | ✘ | passages | ✘ | an answer from evidence, or "insufficient" / "multiple defensible" |
| **S5 Verification** | [s5](prompts/s5-verification.md) | ✔ | ✔ | ✔ | passages | S4 | key vs evidence, every option, alternatives, disagreement type, premises, notes, temporal, frame |
| **S5b Second verifier** | same prompt, other model | ✔ | ✔ | ✔ | passages | ✘ (no S4, no S5) | same schema, independently |
| **S6 Quality** | [s6](prompts/s6-quality.md) | ✔ | ✔ | ✔ | ✘ | ✘ | wording issues, leak, distractors, difficulty, audience, rewrite |
| **S7 Challenge** | [s7](prompts/s7-challenge.md) | ✔ | ✔ | ✔ | passages | everything | typed objections tied to passages |
| **S8 Rules** | *(code, §9)* | | | | | structured fields only | claim statuses, verdict, strength, flags, routing, reasons |

Why S3 does not see the key: extraction asks *"what does this passage say the answer is?"* (`asserted_answer`),
not *"does this passage support the key?"*. A passage cannot be read as support simply because the model was
looking for support. S5 later compares asserted answers with the key.

Why S1b may see the note but S1a may not: notes often contain or imply the answer ("Angel Falls in Venezuela
drops almost 1,000 metres"). Note claims get their own extraction pass (S3 mode B) so they never contaminate
the blind answer pass.

### Retrieval rules (S2, code)

1. **Direct sources first** when S1 names them: Qur'an verse lookup (local corpus, both numbering schemes,
   Arabic + the edition's translation), hadith by collection/number, Wikidata properties.
2. Blind queries (S1a) are always run. Challenge queries (S1b) are run **in addition**, never instead.
3. Per query: top results → drop excluded domains (tier X) → fetch up to *k* documents per claim
   (depth setting: 3 / 5 / 8) preferring higher tiers and distinct origins → extract main text → store with hash.
4. Snippets choose what to fetch; they are never evidence.
5. If S8 finds evidence insufficient and depth allows, one escalation round runs queries suggested by
   S5/S7 (`missing_evidence` fields).

---

## 4. What evidence each claim type needs

This table is configuration (`config/evidence_requirements.yaml`), applied by code. It answers *"what would
we need to see to be entitled to say this is right?"* — before any searching.

| Claim type | Sufficient positive evidence ("STRONG") | Not sufficient on its own | Extra checks |
|---|---|---|---|
| `scripture_content` | The verse itself (P) under the edition's numbering, whose text supports the claim | Any website saying "the Qur'an says…" | Numbering scheme; translation differences noted |
| `hadith_or_tradition` | The narration in a named collection (P, e.g. a hadith reference site) **or** ≥ 2 independent S sources citing it **or** a frame-authority publication citing it (§13.2) | General Islamic websites without a reference | Record grading if available; a hedge in the question ("by tradition") changes the claim (§6) |
| `attribution` | The person's own work (P) or the frame authority's publication quoting it | Third parties' summaries of what they said | Correct work and context |
| `doctrine` (frame) | ≥ 1 frame-authority source (P/S) | Non-frame sources (recorded as context) | Mark `contested_outside_frame` when non-frame sources differ |
| `historical_event`, `biography` | 1 P **or** ≥ 2 independent origins incl. ≥ 1 S | Two pages repeating one encyclopaedia | Dates: check calendar/era conventions |
| `measurement_or_superlative` | The measuring/recording authority (P) **or** ≥ 2 independent S/T origins, **and** competitor check done | Any single list of "tallest X" | Definition used (uninterrupted drop? including cold deserts?); runner-up evidence |
| `statistic_current` | Statistical agency / UN (P) with an as-of date | Undated pages | `as_of` required; estimate vs census |
| `sports_record` | Governing body / league official stats (P) **or** ≥ 2 independent reputable S | Fan sites, quiz sites | `as_of` required; season length / competition scope |
| `definition_or_meaning` | ≥ 2 independent reference works (dictionaries, encyclopaedias) | One travel site | Transliteration variants |
| `classification_or_list` | ≥ 2 independent reference works | | List membership is convention — record whose list |
| `geography_fact`, `science_fact` | 1 P (agency, survey, institution) **or** ≥ 2 independent origins incl. ≥ 1 S **or** ≥ 2 independent T origins (low-risk facts) | One wiki page | Boundaries/conventions (continent borders) |

**MODERATE** = some independent support but below the row's bar. **WEAK** = one origin. **NONE** = no grounded
support. Only STRONG allows VERIFIED.

---

## 5. Sources: tiers, origins and independence

### 5.1 Tiers (per claim, not per website)

| Tier | Meaning | Examples |
|---|---|---|
| **P — primary** | The thing itself or the body that records/measures it | Qur'an text; a hadith collection; the author's own book; FIFA/Premier League records; UN DESA population data; a national survey's height measurement |
| **S — secondary** | Expert work drawing on primary sources | Scholarly books and journals, university pages, museum and archive publications, reputable newspapers reporting a record, official organisation histories |
| **T — tertiary** | Summaries of S/P | Encyclopaedias (Britannica, Wikipedia), reputable educational sites, reference handbooks |
| **X — excluded** | Not evidence | Quiz/trivia/"fun facts" sites, listicles, content farms, forums, Q&A sites, social media, pages that look AI-generated, other quiz datasets |

Tier comes from three places, in order: (1) direct-source lookups are P; (2) the domain registry
(`config/sources.yaml`) gives a default tier per domain and profile; (3) S3 classifies the *page*
(`page_kind`) — which can only **lower** the registry tier (a newspaper's quiz page is X), never raise it.
The same site can be P for one claim and T for another: alislam.org hosting *Jesus in India* is P for an
attribution claim about that book, and S for a general history question.

**Frame authority** is a separate flag, defined per edition profile (e.g. alislam.org, Review of Religions,
the Ahmadiyya translation and commentary of the Qur'an). It is required for `doctrine` and
`attribution_to_frame` claims and counts as P/S for them; it gets no special weight for universal claims.

### 5.2 Origins — the core defence against echoes

Independence is counted by **origin of the fact**, not by number of websites:

1. S3 records `attributed_origin` for each passage: whom the page credits ("according to Ethnologue", a
   footnote to a hadith collection, "FIFA said").
2. Passages are grouped into **origin clusters**: same attributed origin → one cluster; otherwise same
   publisher → one cluster; near-identical wording across sites (similarity ≥ 0.85) → one cluster
   (copying).
3. A Wikipedia passage with a visible citation joins the cluster of that citation.
4. Counting rules in §4 use **clusters**. Five sites quoting Ethnologue are one origin
   (World Tour #102 — *"Which language is spoken by the most people in the world, counting second-language
   speakers?"* — is a real case: almost every page traces back to Ethnologue's estimate).

When all support for a claim comes from one origin, the best possible strength is WEAK, or MODERATE if that
origin is P. The UI shows this plainly: *"All 6 supporting pages trace back to one source."*

---

## 6. Contradictions: classify, then resolve

When passages disagree, S5 classifies the disagreement. The class decides what happens; nothing is resolved by
majority vote or by choosing a validator.

| Class | What it is | Resolution | Dataset example |
|---|---|---|---|
| `factual_conflict` | Same definition, same scope, different value | Weight by tier and independent origins. Clear weight against the key → **INCORRECT**. Comparable weight on both sides → **CONTESTED** | Football Quest #66: key "34 goals"; the evidence is expected to say Haaland scored 36 (34 was the older record in 42-game seasons) |
| `definitional` | Sources measure different things | If the question states the definition, judge under it. If not → **AMBIGUOUS** + rewrite that states it | World Tour #56 "tallest waterfall" (Angel Falls as tallest *uninterrupted* fall; some sources give Tugela Falls); #52 "largest desert" already states "if you count cold deserts" ✔ |
| `convention` | Numbering, transliteration, calendar, counting conventions | Apply the edition's declared convention; if the edition declares none → **AMBIGUOUS** (convention) | Prophets' Stories #3 note "2:32" = 2:31 in the common numbering; Swab Quest #1 number of Rukus (counts differ between printed editions — to confirm) |
| `interpretive` | Traditions/scholars disagree about meaning or belief | Within-frame judgement + `contested_outside_frame`; never INCORRECT on interpretive grounds alone | Prophets' Stories #140 (identification of Roza Bal) |
| `temporal` | Was true, has changed (or became true at a date) | If the question carries an as-of ("Since 2023") judge at that date; otherwise **OUTDATED** if evidence shows the change | World Tour #48 "Since 2023, which country has the most people" — judged against UN estimates as of 2023 |
| `source_error` | One lower-tier outlier against several higher-tier origins | Ignore for the verdict, record for transparency | Typos, wrong years on a single site |

Hedged wording changes the claim. Prophets' Stories #164 says *"By tradition, what did a spider spin…"*. The
claim is no longer "a spider spun a web" but "a known tradition reports a spider spun a web" — an
attribution claim satisfied by the narration (the note cites Musnad Ahmad). Debates about the narration's
strength are recorded, not counted against the key. The quality stage should **reward** such hedges.

---

## 7. Alternative answers and distractors

- **Open questions:** S1b lists surface variants of the key (*An-Nas / Surat An-Nas / Surah Al-Nas*;
  *Hawwa / Eve*; honorifics removed). S5 classifies alternatives as `equivalent_wording`,
  `transliteration`, `partial_but_acceptable` or `alternative_convention`. Wording differences are never
  grounds for INCORRECT.
- **Long descriptive answers** (Swab Quest #253, #347): S5 splits the key into its factual components and
  checks each; a correct core with a wrong detail is PARTIALLY_CORRECT.
- **Multiple choice:** S3 maps every asserted answer to an option letter, so evidence for distractors is
  collected as a side effect of blind research. A **targeted distractor investigation** (one extra
  query round for that option) is triggered only when:
  - the blind answer picks a distractor or reports `multiple_defensible`;
  - any passage's asserted answer maps to a distractor;
  - S6 flags `distractor_possibly_correct`.
  This avoids proving 21,000 negatives for 7,000 MC questions while still catching the dangerous case.
- **Superlatives** (tallest, largest, most, first) always get a competitor query (*"second tallest
  waterfall"*, *"other cities in Europe and Asia"*), because the typical error is an outdated or
  definition-dependent winner. World Tour #36 (*"Which famous city is split between two continents?"*) shows
  why wording matters: several smaller cities straddle the Europe–Asia boundary; "famous" is what makes
  Istanbul the unique answer — S6 should note the word is load-bearing.

---

## 8. Ambiguity and wording (S6)

Question quality is judged **without evidence**, by a separate prompt, so a good research result cannot hide a
bad question and vice versa. Issues are typed (see the S6 schema), the main ones being:

- `multiple_answers_possible`, `ambiguous_wording`, `missing_context_or_convention`;
- `false_precision` (exact numbers in questions that sources give approximately);
- `compound_question` — two claims in one question, where one can be wrong (Swab Quest #247 *"first human being
  and first Prophet"*; Football Quest #66 "how many **and** who");
- `answer_leak`, `implausible_distractors`, `distractor_possibly_correct`, `too_few_options`
  (several Swab Quest / Football Quest questions have three options);
- `difficulty_mismatch`, `age_inappropriate` (the editions mix ages 5+ to adults), `culturally_misleading`,
  `honorific_or_style_inconsistent` (edition style: "Hadhrat Adam (as)").

S6 proposes a rewrite only for NEEDS_IMPROVEMENT or POOR, and keeps the question's intent and difficulty.

---

## 9. From findings to verdict (S8, code)

### 9.1 Claim status

For each claim (K, each PR, each N), computed from grounded passages after origin clustering:

| Status | Rule |
|---|---|
| `supported` | support meets the §4 bar for the claim type (STRONG) and no material contradiction |
| `supported_weak` | some support (MODERATE/WEAK), no material contradiction |
| `contradicted` | contradicting evidence meets the §4 bar and outweighs support (tier, then origins) |
| `contested` | both sides meet the bar (factual_conflict or interpretive outside the frame) |
| `definition_dependent` | disagreement classified definitional/convention, not settled by the question or edition |
| `outdated` | temporal: previously supported, later change supported |
| `unverified` | nothing above |

For the key claim, "support" additionally requires that **passages' asserted answers equal the key** (or an
accepted equivalent) — a passage that merely mentions the key's entity does not count.

### 9.2 Question verdict (first matching row wins)

| # | Condition | Verdict | Defect location |
|---|---|---|---|
| 1 | any presupposition `contradicted` | **INCORRECT** | `question_premise` |
| 2 | key `contradicted` | **INCORRECT** | `answer` |
| 3 | key `outdated` and question has no as-of qualifier | **OUTDATED** | `answer` |
| 4 | key `contested` **or** any presupposition `contested` | **CONTESTED** | — |
| 5 | MC: ≥ 2 options supported, or open: ≥ 2 non-equivalent answers supported; **or** key/premise `definition_dependent` | **AMBIGUOUS** | `question_wording` / `options` |
| 6 | key `supported` **and** blind answer = key (or equivalent) **and** all presuppositions `supported` or not material **and** no decisive grounded objection (S7) **and** S5/S5b both CORRECT | **VERIFIED** | — |
| 7 | otherwise | **UNVERIFIED** | — |

Note claims do not change the question verdict; they get their own `note_status`
(`supported / contradicted / convention_mismatch / unverified`) because a wrong note is fixed differently
from a wrong question. Quality (`GOOD / NEEDS_IMPROVEMENT / POOR`) is reported alongside, never mixed in.

`within_frame` (true for frame-specific claims judged against frame authorities) and
`contested_outside_frame` are flags on the verdict, so "VERIFIED (within frame, contested outside)" is a
normal, honest outcome for #140.

### 9.3 Review routing

| Route | When |
|---|---|
| `needs_review` | verdict ∈ {INCORRECT, AMBIGUOUS, CONTESTED, OUTDATED}; S5 ≠ S5b on factual accuracy; blind answer ≠ key; decisive S7 objection; note `contradicted`; quality POOR |
| `needs_specialist` | frame_class ∈ {frame_specific, attribution_to_frame} or claim type ∈ {scripture_content, hadith_or_tradition, doctrine} **and** anything other than a clean VERIFIED |
| `auto_ok` | VERIFIED, STRONG, verifiers agree, no flags — still listed and reversible |
| `audit_sample` | a random 5 % of `auto_ok` per run goes to review anyway, to measure the false-verification rate |

`reasons` lists every rule that fired in plain words, e.g. *"Blind answer (36 goals, Haaland) differs from key
(34 goals, Haaland). Two independent official/reputable origins support 36. Classified: factual_conflict."*

---

## 10. Edition profiles (frames)

Draft for two editions; the religious ones need confirmation by the edition's reviewer.

```yaml
# config/profiles/prophets-stories.yaml
edition: prophets-stories
audience: families, ages 5+
frame:
  name: Ahmadiyya understanding
  applies_to: [doctrine, attribution_to_frame, frame_specific]
  authorities:            # frame authority for doctrine/attribution claims
    - alislam.org
    - reviewofreligions.org
    - "The Holy Qur'an with English translation and commentary (Ahmadiyya)"
conventions:
  quran_numbering: bismillah_is_verse_1     # 2:32 here = 2:31 in the common (Hafs/Cairo) numbering
  honorifics_in_answers: ignore              # "Hadhrat Adam (as)" == "Adam"
  transliteration: lenient                   # Isma'il / Ismail / Ishmael
direct_sources: [quran, hadith]
review:
  specialist_for: [doctrine, scripture_content, hadith_or_tradition, frame_specific, attribution_to_frame]
```

```yaml
# config/profiles/world-tour.yaml
edition: world-tour
audience: families, ages 5+
frame: none
conventions:
  superlatives: require_definition           # tallest/largest must say how it is measured if sources differ
  as_of_default: dataset_import_date
direct_sources: [wikidata]
```

---

## 11. Worked examples from the dataset

These are the expectations I would encode in the evaluation set. They are **my hypotheses to be confirmed by
evidence** — which is exactly what an eval label is. Where I am unsure, it says so.

| Edition #id | Question (short) | Key | What the method should do | Expected outcome |
|---|---|---|---|---|
| World Tour #120 | Since 2010, tallest building? | Burj Khalifa | Superlative + as-of in question; competitor query; P/S sources easy | **VERIFIED**, STRONG, auto_ok |
| World Tour #135 | Kilimanjaro's country? | Tanzania | Distractor Kenya is plausible (shares the border/view); blind answer decides | **VERIFIED**; S6: good distractors |
| World Tour #151 | Ancient wonder still standing? | Great Pyramid | Classification claim; all distractors destroyed — evidence arrives as a side effect | **VERIFIED** |
| Football Quest #66 | Most PL goals in one season, and who? | 34 — Haaland 2022–23 | Blind answer: 36 (expected); 34 is the old 42-game-season record — a classic echo-mix | **INCORRECT** (answer), PARTIALLY_CORRECT, suggest "36 goals — Erling Haaland, 2022–23" |
| Football Quest #70 | Which nation won three *consecutive* WCs: 1958, 1962, 1970? | Brazil | Presupposition "consecutive" tested separately; 1966 was won by England | **INCORRECT** (question_premise), key entity correct; rewrite drops "consecutive" |
| Football Quest #73 | Won World Player of the Year three times in a row (1996, 1997, 1998)? | Ronaldo | Presupposition dates tested; 1998 winner expected to be Zidane; Ronaldo's third was 2002 | **INCORRECT** (question_premise) |
| Football Quest #86 | Club with most English doubles? | Man Utd, 3 | Blind answer expected `multiple_defensible` (Arsenal also 3); wording garbled ("How many clubs…") | **AMBIGUOUS**, quality POOR, rewrite |
| World Tour #56 | Tallest waterfall? | Angel Falls | Superlative competitor query finds Tugela claims; classify definitional vs factual | Probably **VERIFIED** with S6 suggesting "highest uninterrupted"; **AMBIGUOUS** if strong sources dispute |
| World Tour #102 | Most-spoken language incl. second language? | English | Question states the definition ✔; `measurement_or_superlative`; origin clustering → mostly one origin (Ethnologue, registered as S: it compiles estimates rather than measuring); time-sensitive estimate | **VERIFIED** only if ≥ 2 independent origins; otherwise UNVERIFIED (single origin) — shows the echo defence (traced in [s7](prompts/s7-challenge.md)) |
| World Tour #48 | Since 2023, most populous country? | India | statistic_current; P = UN DESA; estimate (no recent census) | **VERIFIED** with as_of 2023; S6 may suggest "According to UN estimates" |
| World Tour #52 | Largest desert, counting cold deserts? | Antarctica | Definition stated in question → definitional conflict resolved by the question | **VERIFIED** |
| Prophets' Stories #3 | What did Allah teach Adam? | The names of all things | Direct lookup: note "2:32" under bismillah_is_verse_1 → common 2:31 | **VERIFIED**; note **supported** (convention applied). Without the profile: note `convention_mismatch` — the method must not call it wrong |
| Prophets' Stories #2 | Name of Adam's wife? | Hawwa (Eve) | Open; equivalents Hawwa/Eve/Hawa; note claim "known from hadith" needs a hadith reference (S3 mode B) | Question **VERIFIED** likely; note **unverified** unless a narration is found → needs_specialist |
| Prophets' Stories #138 | According to the Promised Messiah (as), did Isa (as) die on the cross? | No — survived | `attribution_to_frame`; P = *Jesus in India*; non-frame disagreement irrelevant | **VERIFIED** (no contested flag: the question is about the teaching) |
| Prophets' Stories #140 | City of the tomb of Isa (as), shrine of Yuz Asaf? | Srinagar | Universal part (shrine in Srinagar) + `frame_specific` premise | **VERIFIED**, within_frame, contested_outside_frame → needs_specialist only if the reviewer wants the wording checked |
| Prophets' Stories #164 | By tradition, what did a spider spin at Thawr? | A web | Hedge → attribution to tradition; note cites Musnad Ahmad | **VERIFIED** as tradition; grading recorded |
| Swab Quest #247 | First human being **and** first Prophet? | Hadhrat Adam | Compound; Ahmadiyya literature discusses whether Adam was the first human (to confirm with the reviewer); compare PS #1, which asks only "first prophet" | **needs_specialist**; S6: compound_question; possibly AMBIGUOUS within frame |
| Swab Quest #1 | How many Rukus in the Qur'an? | 540 | Counting convention; figures may differ between printed editions (to confirm) | VERIFIED under the edition's convention or **AMBIGUOUS** (convention) |
| Swab Quest #70 | City the Musleh Maud (ra) called his second home? | Lahore | Thin evidence expected; 3 options | Likely **UNVERIFIED** → needs_specialist; S6: too_few_options |

### Traced example A — the echo trap (Football Quest #66)

1. **S1a** (no key): information need *"most goals by one player in a single Premier League season; number,
   player, season"*; `sports_record`; time-sensitive; presupposition: none; interpretations: *38-game vs
   42-game seasons*; queries: `Premier League record most goals in a single season`,
   `Premier League golden boot record goals 38-game season`, `most goals in a Premier League season list`.
2. **S1b** (sees key): key claim *"Haaland scored 34 … the most"*; challenge queries:
   `Haaland 2022-23 Premier League goals total`, `Andy Cole Alan Shearer 34 goals record`.
3. **S2**: fetches the league's own records page (P), two reputable sports news reports (S), Wikipedia (T);
   discards two quiz sites (X).
4. **S3** (no key): each passage's `asserted_answer` — e.g. the league page asserts *36, Haaland, 2022–23*; a
   news report asserts *36 … breaking the 34 set by Cole and Shearer*.
5. **S4** (no key): `answered` → *"36 goals — Erling Haaland, 2022–23"*.
6. **S5**: key vs blind → `partially_overlapping` (player right, number wrong); `factual_conflict`;
   PARTIALLY_CORRECT; suggested answer *36*.
7. **S8**: key `contradicted` by P + independent S → row 2 → **INCORRECT**, defect `answer`, needs_review.

A naive system searching "Haaland 34 goals Premier League record" would very likely have found pages
mentioning 34 and Haaland together and accepted it. Here the key never reached the query writer or the
reader.

### Traced example B — convention, not error (Prophets' Stories #3)

1. S1a: `scripture_content`, `tradition_general`; direct lookup suggested from the question: none (the
   question names no verse).
2. S1b: note claim N1 *"Al-Baqarah verse 32 (edition numbering) is where Allah teaches Adam the names"*;
   direct lookup `quran 2:32 scheme=bismillah_is_verse_1` → corpus maps to common 2:31.
3. S3 mode A: Qur'an text + tafsir pages; asserted answer *"the names (of all things)"*.
4. S3 mode B on N1: verse text P supports.
5. S5: key CORRECT; note `supported`; disagreement `convention` (some pages cite 2:31) — resolved by profile.
6. S8: **VERIFIED**, note supported, needs_specialist? No — clean VERIFIED.

### Traced example C — attribution vs belief (Prophets' Stories #138 vs #140)

- #138 → S1a `attribution_to_frame`. Evidence requirement: the author's own work (P). Non-frame sources
  describing Christian belief are `mentions`, not contradictions. → VERIFIED, no contested flag.
- #140 → S1a `frame_specific` premise *"the tomb of Hadhrat Isa (as)"* + universal claim *"shrine known as
  Yuz Asaf / Roza Bal in Srinagar"*. Universal claim: STRONG from independent S/T. Premise: frame authority
  supports; non-frame sources disagree → `interpretive`. → VERIFIED, `within_frame`,
  `contested_outside_frame`. The reviewer decides whether the edition wants softer wording; the tool does not
  decide that.

### Traced example D — false premise with a "right" answer (Football Quest #70)

S1a extracts PR1 *"Brazil/some nation won three consecutive World Cups in 1958, 1962, 1970"* — separately
from the information need. Evidence: 1966 won by England (P/S). PR1 `contradicted` → row 1 → **INCORRECT**,
defect `question_premise`, even though "Brazil" is the right nation for the years listed. Suggested question:
*"Which nation won the World Cup in 1958, 1962 and 1970?"*

---

## 12. How we will know it works

1. **Eval set** (`eval/`): ≈ 150 real questions with human labels (verdict, defect location, alternatives)
   — including every row of §11 — plus ≈ 50 **seeded errors** made by editing correct questions: wrong year,
   wrong number, swapped key index, false premise inserted, a distractor made correct, a wrong verse number
   in a note, a changed definition.
2. **Metrics per run of the eval:**
   - error recall: seeded + known errors that end in INCORRECT/AMBIGUOUS/CONTESTED/OUTDATED or `needs_review`
     (target ≥ 90 %);
   - false alarm rate: known-good questions marked INCORRECT (target ≤ 3 %);
   - false verification rate: known-bad questions marked VERIFIED (target ≈ 0; every case investigated);
   - grounding failure rate (target < 2 %), blind-answer insufficiency rate, S5/S5b disagreement rate.
3. **Every change to a prompt, model, registry or rule re-runs the eval**; results are stored per version.
4. **Audit sample** in production runs (§9.3) estimates the false-verification rate on real data.

---

## 13. Decisions on the open points (Mojeeb, 2026-11-16)

1. **Frame authorities** (Swab Quest, Prophets' Stories): alislam.org — including its book library
   (new.alislam.org/library; downloaded books go into the local PDF library) and the Qur'an at
   alislam.org/quran/app with the **Maulawi Sher Ali** English translation — plus alhakam.org (e.g. the
   *Prophets of Allah* series) and reviewofreligions.org. Other editions use web search; for the non-religious
   editions any reputable site counts, Wikipedia included (registry tiers in `config/sources.yaml`).
2. **Hadith**: when an Ahmadiyya book cites the original collection, use that reference; otherwise the
   frame-authority book itself is enough (its references are checked by scholars) → `hadith_or_tradition` is
   STRONG with one frame-authority source as well (`config/evidence_requirements.yaml`).
3. **Wording** (#247 and similar): most questions were AI-generated; wording may be changed freely. Questions that
   have different right answers depending on context are to be reworded or given more context — S6 findings
   about ambiguity are real work items, not noise.
4. **Qur'an numbering**: always the Ahmadiyya numbering — Bismillah is verse 1 of each chapter
   (`quran_numbering: bismillah_is_verse_1`).
5. **Spot check**: 5 % of `auto_ok` questions (`audit_sample_percent: 5`). The review step goes through every
   question anyway.
