# AI Question Validation Platform
## Product Requirements and Technical Development Specification

**Project objective:** Build a local web application that validates factual accuracy and quality of quiz questions using independent AI research and authoritative online sources.

**Initial input:** CSV files containing 2,000–10,000 questions.

**Primary objective:** Identify incorrect, ambiguous, outdated or insufficiently supported questions and provide evidence-based recommendations for corrections.

---

# 1. Product Vision

Build a reusable AI-powered Question Validation Platform.

The application should allow a user to import an existing quiz dataset, automatically investigate each question, evaluate its expected answer, identify potential problems and produce a structured validation report.

The application must not blindly trust the AI model that originally generated the questions.

It must independently research the underlying facts and provide verifiable evidence for its conclusions.

The application should be designed for different quiz editions and subjects, including:

- General knowledge
- History
- Geography
- Science
- Religion
- Islamic knowledge
- Ahmadiyya-specific knowledge
- Sports
- Entertainment
- Technology
- Other subjects

The architecture must not assume that all questions have the same validation requirements.

# 2. Input Data Format

The application must support CSV files with the following columns:

| Column | Description |
|---|---|
| id | Unique question identifier |
| question | Question text |
| type | Question type: multi or open |
| answer | Expected answer or correct option index |
| opt_a | First answer option |
| opt_b | Second answer option |
| opt_c | Third answer option |
| opt_d | Fourth answer option |
| difficulty | easy, medium or hard |
| category | Main category |
| subcategory | Subcategory |
| topic | Specific topic |
| note | Additional context |

Example:

id,question,type,answer,opt_a,opt_b,opt_c,opt_d,difficulty,category,subcategory,topic,note

The application must preserve all original columns and values.

## 2.1 Question types

### Multiple choice (multi)

The answer field represents the index of the correct option.

Mapping:

- 1 = opt_a
- 2 = opt_b
- 3 = opt_c
- 4 = opt_d

The application must resolve the expected answer into its actual text before performing factual validation.

It must also verify that:
- The answer index is valid.
- The corresponding option exists.
- The correct option is factually accurate.
- Incorrect options are genuinely incorrect.
- There is only one defensible correct answer.
- No other option could reasonably be considered correct.

### Open questions (open)

The answer field contains free-text expected answers.

The application must support semantically equivalent answers.

For example:

Question: What is the name of the last Surah in the Holy Qur'an?

Expected answer: Surah An-Nas.

A response such as "An-Nas" or "Surat An-Nas" should be treated as equivalent.

The application should distinguish between:
- Fully correct answers.
- Partially correct answers.
- Acceptable alternative answers.
- Incorrect answers.
- Answers requiring additional context.

# 3. Application Architecture

Build a local web application.

Recommended technology:

- Python 3.12+
- Streamlit for the user interface.
- SQLite for persistent storage.
- SQLAlchemy for database access.
- Pydantic for structured AI responses.
- Pandas for CSV processing.
- Configurable AI provider integration.
- Configurable web search provider integration.

Keep the application modular.

Suggested project structure:

question-validator/
  app.py
  config.py
  requirements.txt
  .env.example

  models/
    question.py
    validation.py
    source.py
    dataset.py

  services/
    csv_importer.py
    csv_exporter.py
    question_analyzer.py
    research_service.py
    verification_service.py
    quality_service.py
    review_service.py

  providers/
    base_ai_provider.py
    anthropic_provider.py
    openai_provider.py
    base_search_provider.py
    tavily_provider.py

  prompts/
    question_analysis.md
    factual_research.md
    answer_verification.md
    question_quality.md
    independent_review.md

  database/
    database.py
    repositories.py

  ui/
    pages/
      dashboard.py
      import_dataset.py
      validation_settings.py
      validation_results.py
      question_review.py
      export.py

  tests/

  data/
    validation.db
    imports/
    exports/

The application should support running locally without Docker initially. Docker support can be added later.

# 4. Main Application Features

## 4.1 Dataset Import

Provide an interface to:

- Upload CSV files.
- Preview the imported questions.
- Validate required columns.
- Detect malformed rows.
- Detect duplicate IDs.
- Detect missing answers.
- Detect invalid multiple-choice indexes.
- Detect missing options.
- Identify duplicate or very similar questions.

Before starting validation, show a dataset summary:

- Total questions.
- Number of open questions.
- Number of multiple-choice questions.
- Number of categories.
- Number of missing or invalid fields.
- Number of duplicate questions.

Allow the user to confirm the import.

Never overwrite the original file.

## 4.2 Dataset Management

Allow users to:

- View imported datasets.
- Rename datasets.
- Delete datasets.
- View previous validation runs.
- Resume interrupted validation runs.
- Revalidate selected questions.
- Compare validation results between runs.

Every imported dataset must have its own identifier.

Every validation run must record which dataset version it used.

## 4.3 Validation Configuration

Before starting validation, allow the user to configure:

- AI provider.
- Research provider.
- Research depth.
- Number of independent sources required.
- Whether to perform independent AI review.
- Which categories require special source restrictions.
- Whether human review is mandatory for selected categories.

Default configuration:

- Two independent supporting sources where reasonably available.
- Prefer primary and authoritative sources.
- Independent AI verification enabled.
- Question-quality assessment enabled.
- Human review required for unresolved or disputed claims.

The application must support different validation profiles.

For example:

**General knowledge profile**
- Encyclopaedias.
- Official institutions.
- Government sources.
- Academic sources.

**Islamic knowledge profile**
- Primary religious texts.
- Authenticated Hadith collections where relevant.
- Recognized scholarly references.
- Official Ahmadiyya sources for questions specifically about Ahmadiyya beliefs, history and teachings.

The system must not assume that an official organizational source is automatically the final authority on every religious or historical question.

# 5. Validation Pipeline

The validation process must consist of separate stages.

Do not implement everything in one large AI prompt.

## Stage 1: Structural Validation

Validate the CSV structure and question format.

Checks:

- Valid question type.
- Valid answer format.
- Valid option indexes.
- Required fields.
- Duplicate questions.
- Duplicate IDs.
- Missing values.

This stage should not require AI or web searches.

## Stage 2: Question Analysis

Analyze the question before researching it.

Extract:

1. The underlying factual claim.
2. What exactly the question is asking.
3. The expected answer.
4. Relevant contextual information from the note field.
5. Whether the question depends on a date, location, definition or particular convention.
6. Whether there are potentially multiple interpretations.

For religious questions, identify whether the question concerns:
- General Islamic knowledge.
- Qur'anic knowledge.
- Hadith.
- Islamic history.
- Ahmadiyya teachings.
- Ahmadiyya history.
- Differences of scholarly interpretation.

Output a structured analysis.

## Stage 3: Independent Web Research

Research the factual claim independently.

Do not simply search for the expected answer and accept the first result.

The research process should:

1. Identify appropriate search queries.
2. Search for reliable sources.
3. Prefer primary sources.
4. Retrieve relevant source content.
5. Compare information across sources.
6. Identify contradictions.
7. Record supporting and opposing evidence.

Search should be adapted to the category.

Examples:

Science:
- Scientific institutions.
- Research publications.
- Universities.
- Government science agencies.

History:
- National archives.
- Museums.
- Historical documents.
- Academic publications.

Sports:
- Official governing bodies.
- Official league records.
- Federation statistics.

Religion:
- Primary religious sources.
- Recognized religious reference works.
- Relevant scholarly sources.
- Official Ahmadiyya publications for specifically Ahmadiyya questions.

Never treat a search-engine snippet as sufficient evidence.

Save the source URL, title, relevant excerpt and retrieval date.

If reliable evidence cannot be found, mark the question as unverified.

## Stage 4: Factual Answer Verification

Compare the original expected answer with the independently collected evidence.

Evaluate:

- Is the answer factually correct?
- Is it partially correct?
- Is there an acceptable alternative answer?
- Is the answer dependent on a particular interpretation?
- Is the question itself based on a false premise?
- Is the expected answer outdated?
- Do reliable sources disagree?

For multiple-choice questions, evaluate every option.

For open questions, identify acceptable alternative answers.

Do not mark a question incorrect merely because the wording of the expected answer differs from the wording in a source.

## Stage 5: Question Quality Assessment

Assess the question independently of whether its expected answer is correct.

Check:

- Is the question understandable?
- Is it sufficiently precise?
- Does it contain ambiguous wording?
- Does it accidentally reveal the answer?
- Is there more than one possible correct answer?
- Are the multiple-choice distractors plausible but incorrect?
- Is the question appropriate for its difficulty level?
- Does the question require an unstated assumption?
- Is the question culturally or contextually misleading?

Provide a suggested rewrite when necessary.

## Stage 6: Independent AI Review

Use a second independent AI assessment.

The second model should receive:

- Original question.
- Expected answer.
- Question category.
- Extracted factual claim.
- Research evidence.
- First model's verdict and reasoning.

Its purpose is to challenge the first model.

Ask it to identify:

- Incorrect interpretations.
- Unsupported conclusions.
- Missing evidence.
- Alternative answers.
- Conflicting sources.
- Potential hallucinations.
- Weak reasoning.

The second model must be allowed to disagree.

Do not automatically resolve disagreements by choosing the first model or the second model.

Mark disputed results for human review.

# 6. Validation Result Structure

Every question must have a structured validation result.

Suggested Pydantic model:

QuestionValidation:
  question_id: string

  verdict:
    VERIFIED
    INCORRECT
    AMBIGUOUS
    UNVERIFIED
    OUTDATED
    REVIEW_REQUIRED

  evidence_strength:
    STRONG
    MODERATE
    WEAK
    NONE

  factual_accuracy:
    CORRECT
    PARTIALLY_CORRECT
    INCORRECT
    UNCERTAIN

  answer_uniqueness:
    UNIQUE
    MULTIPLE_VALID_ANSWERS
    UNCERTAIN

  question_quality:
    GOOD
    NEEDS_IMPROVEMENT
    POOR

  explanation: string

  factual_claim: string

  suggested_answer: string | null

  suggested_question: string | null

  acceptable_alternatives: list[string]

  ambiguity_explanation: string | null

  sources: list[SourceEvidence]

  research_date: datetime

  independent_review:
    verdict: string
    explanation: string

  human_review_required: boolean

SourceEvidence:
  title: string
  url: string
  publisher: string
  source_type: string
  relevant_excerpt: string
  supports_claim: boolean
  reliability_assessment: string

All AI outputs must be validated against the expected schema.

Invalid or incomplete responses must be retried or flagged, never silently accepted.

# 7. Validation Verdict Rules

Use the following definitions.

VERIFIED:
The expected answer is supported by reliable evidence and no significant unresolved ambiguity exists.

INCORRECT:
Reliable evidence contradicts the expected answer.

AMBIGUOUS:
The question has multiple defensible interpretations or answers.

UNVERIFIED:
There is insufficient reliable evidence to establish the answer.

OUTDATED:
The answer was previously correct but has changed.

REVIEW_REQUIRED:
The question requires specialist knowledge, has conflicting sources or has an unresolved disagreement between validators.

Important:

An absence of contradictory evidence is not proof that an answer is correct.

A question should only be marked VERIFIED when positive supporting evidence has been identified.

A numerical AI confidence score must not be treated as a calibrated probability of correctness.

# 8. AI Prompt Design

Keep prompts in separate files so they can be improved without changing the application code.

## Prompt A: Question Analysis

You are an expert quiz question analyst.

Analyze the supplied question and expected answer.

Your task is to identify exactly what factual claim is being tested.

Do not attempt to validate the answer yet.

Consider the category, subcategory, topic and additional notes.

Identify:
- The central factual claim.
- Important assumptions.
- Relevant definitions.
- Potential ambiguity.
- Whether the question is time-sensitive.
- Whether a particular scholarly, historical or technical convention is required.

For religious questions, distinguish between general Islamic knowledge and Ahmadiyya-specific knowledge.

Return structured JSON.

Do not invent facts or make unsupported assumptions.

## Prompt B: Independent Research

You are an independent factual research assistant.

Research the following factual claim using online sources.

The expected answer is provided only as context. Do not assume it is correct.

Your objectives:

1. Find authoritative sources relevant to the claim.
2. Prefer primary sources.
3. Find independent corroboration where possible.
4. Identify contradictory information.
5. Identify definitions or conventions that could explain different answers.
6. Record relevant evidence and source URLs.
7. Distinguish established facts from interpretations and opinions.

Do not rely on search snippets alone.

Do not fabricate URLs, quotations, source names or publication details.

If you cannot find reliable evidence, clearly state that.

Return structured JSON containing the research findings and source evidence.

## Prompt C: Factual Verification

You are an independent factual accuracy evaluator.

Your task is to determine whether the supplied expected answer is supported by the supplied research evidence.

Do not assume the original answer is correct.

Evaluate:
- Factual correctness.
- Supporting evidence.
- Contradictory evidence.
- Alternative answers.
- Ambiguity.
- Relevant qualifications.

For multiple-choice questions, evaluate all available options.

For open questions, identify acceptable equivalent answers.

Do not reject an answer simply because different wording is used.

Only use the supplied evidence. If evidence is insufficient, mark the result UNVERIFIED.

Return a structured validation result.

## Prompt D: Question Quality

You are an expert quiz editor.

Evaluate the quality of this question independently of its factual answer.

Check:
- Clarity.
- Precision.
- Ambiguity.
- Multiple possible answers.
- Quality of distractors.
- Difficulty appropriateness.
- Missing context.
- Potentially misleading wording.

Suggest a better version where appropriate.

Do not unnecessarily rewrite questions that are already good.

Return structured JSON.

## Prompt E: Independent Challenge Review

You are an independent reviewer tasked with challenging a previous factual verification.

You have been given the original question, expected answer, research evidence and first validator's conclusion.

Do not simply agree with the first validator.

Try to find weaknesses in its reasoning.

Investigate:
- Whether the evidence actually proves the answer.
- Whether the sources are authoritative.
- Whether sources are genuinely independent.
- Whether an important alternative interpretation was overlooked.
- Whether contradictory evidence was ignored.
- Whether the question itself contains a false premise.
- Whether the first validator confused similar facts.

You must be willing to disagree.

Return your independent verdict and explanation.

If evidence is insufficient, say so rather than guessing.

# 9. User Interface

The application should have the following pages.

## Dashboard

Display:

- Total imported questions.
- Questions validated.
- Questions remaining.
- Verified.
- Incorrect.
- Ambiguous.
- Unverified.
- Outdated.
- Review required.

Include progress indicators and category summaries.

## Import Dataset

Upload CSV files.

Preview the questions and validate the format before importing.

## Validation Settings

Configure:
- AI provider.
- Research provider.
- Research depth.
- Source requirements.
- Independent review.
- Category-specific source preferences.
- Batch size.
- Maximum concurrent tasks.
- API request limits.

## Validation Results

Display a filterable table.

Filters:
- Dataset.
- Category.
- Subcategory.
- Topic.
- Difficulty.
- Question type.
- Verdict.
- Human review status.

Allow sorting by question ID and validation status.

## Question Review

Provide a detailed view of an individual question.

Display:

- Original question.
- Original answer.
- All multiple-choice options.
- Extracted factual claim.
- Research findings.
- Supporting sources.
- Contradictory sources.
- First validator's assessment.
- Independent reviewer assessment.
- Suggested correction.
- Question-quality assessment.

Provide actions:

- Approve original question.
- Approve suggested correction.
- Edit question manually.
- Mark as requiring specialist review.
- Reject question.
- Revalidate question.

Human decisions must be saved separately from AI recommendations.

## Export

Support:

1. Original CSV.
2. Validation report CSV.
3. Excel report with separate worksheets.
4. Corrected CSV containing only explicitly approved changes.

Never automatically replace the original dataset.

# 10. Reliability and Processing Requirements

The application must support thousands of questions.

Implement:

- Batch processing.
- Configurable concurrency.
- Rate-limit handling.
- Exponential backoff.
- Retry handling.
- Persistent intermediate results.
- Resume after interruption.
- Individual question revalidation.
- API cost and token tracking.
- Research result caching.
- Logging and error reporting.

A failed question must not stop the entire dataset.

Each validation stage should save its results before proceeding to the next stage.

Avoid unnecessary repeated research when multiple questions test the same underlying factual claim.

However, cached research must be checked for relevance, freshness and compatibility with the exact question.

Do not assume that two similarly worded questions necessarily test identical facts.

# 11. API and Cost Management

Use provider abstraction so that the AI and search providers can be changed independently.

Support at least:

- Anthropic API.
- OpenAI API.
- A configurable web search provider.

Important distinction:

A Claude subscription used with Claude Code does not automatically provide API access or API usage credits for a separate application.

The application must use separately configured API credentials for runtime processing.

Do not hardcode API keys.

Use environment variables and provide an example configuration file.

Before running a large validation job, allow a small pilot run to estimate costs.

Display:
- Number of research calls.
- Number of AI calls.
- Input and output tokens where available.
- Estimated API cost where provider pricing information is available.
- Actual reported usage where available.

# 12. Testing and Acceptance Criteria

Before considering the application complete, test it with a small dataset.

Tests must include:

1. A clearly correct multiple-choice question.
2. A clearly incorrect multiple-choice answer.
3. An open question with an equivalent alternative answer.
4. An ambiguous question.
5. A question with insufficient evidence.
6. A question with outdated information.
7. A question where two sources disagree.
8. A religious question requiring specialist context.
9. A question where multiple-choice distractors contain another defensible answer.
10. A malformed CSV row.

The application must demonstrate that it can distinguish these cases.

Additional requirements:

- No fabricated sources.
- No invented quotations.
- No automatic approval of unverified questions.
- No silent changes to original data.
- No loss of question metadata.
- Correct mapping of multiple-choice answer indexes.
- Successful recovery from interrupted processing.
- Successful export and re-import of the original CSV structure.

# 13. Development Approach

Implement the project incrementally.

Phase 1: Foundation
- Project structure.
- Database.
- CSV import/export.
- Dataset management.
- Structural validation.

Phase 2: Research
- AI provider abstraction.
- Search provider abstraction.
- Question analysis.
- Research and evidence collection.

Phase 3: Verification
- Factual verification.
- Question-quality assessment.
- Independent review.
- Structured result storage.

Phase 4: User Interface
- Dashboard.
- Validation configuration.
- Results table.
- Individual question review.
- Export functionality.

Phase 5: Reliability
- Resumable processing.
- Retry handling.
- Concurrency.
- Usage tracking.
- Automated tests.

Do not implement everything in one step.

Build and test each phase before continuing.

# 14. Instructions to the Developer

Before implementation:

1. Review this specification.
2. Identify any missing architectural decisions.
3. Propose a concrete implementation plan.
4. Identify potential API limitations and costs.
5. Explain how source evidence will be retrieved and stored.
6. Explain how the system will avoid accepting unsupported AI conclusions.

Prioritize factual reliability over processing speed.

The application should be easy to use, maintainable and reusable for future quiz editions.

Do not overengineer the initial version.

The goal is a dependable question-validation tool, not a general-purpose research platform.