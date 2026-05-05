# Verification Reference

This reference tells an agent how to verify Teacher-skill after changing the Skill, the CLI, prompts, tests, docs, or release packaging.

Use this file when the task is about:

- release readiness
- CI failures
- local test failures
- validating a teaching-loop behavior change
- validating a Skill documentation change
- checking whether the project is safe to publish
- explaining what evidence proves a change is done

Verification should answer one question:

```text
Can another user or agent install, run, understand, and trust this Skill?
```

---

## Table of Contents

- [Verification Mindset](#verification-mindset)
- [Choose the Right Verification Level](#choose-the-right-verification-level)
- [Preflight Checks](#preflight-checks)
- [Test Commands](#test-commands)
- [Behavior Verification](#behavior-verification)
- [Skill Documentation Verification](#skill-documentation-verification)
- [Prompt Verification](#prompt-verification)
- [Storage Verification](#storage-verification)
- [Release Verification](#release-verification)
- [GitHub Actions Verification](#github-actions-verification)
- [Windows and Local Environment Issues](#windows-and-local-environment-issues)
- [Failure Triage](#failure-triage)
- [Evidence to Report](#evidence-to-report)
- [Minimum Acceptance Checklist](#minimum-acceptance-checklist)

---

## Verification Mindset

Do not say “done” just because files were edited.

A change is done only when one of these is true:

1. Relevant tests passed.
2. Manual smoke testing passed.
3. The change is documentation-only and Markdown/path checks passed.
4. Testing was blocked by environment constraints, and the blocker is clearly reported with the exact command that should be run outside the blocked environment.

Never claim the full test suite passed unless it really did.

If only a subset passed, say exactly which subset passed.

If CI passed but local tests were blocked, say CI passed and local was blocked.

If local tests passed but CI has not run yet, say local passed and CI still needs confirmation.

---

## Choose the Right Verification Level

Use the smallest verification level that proves the change, then escalate if risk is higher.

| Change Type | Minimum Verification | Stronger Verification |
|---|---|---|
| `SKILL.md` only | `git diff --check` on the file, read for trigger clarity | install/load the Skill in a fresh context |
| `references/*.md` only | `git diff --check` on the file, path/link sanity | compare with `SKILL.md` to avoid contradiction |
| README/docs only | `git diff --check`, link/path sanity | check release checklist and status docs |
| CLI display only | focused `test_main_flow.py` display-related tests | run `python main.py --check` |
| `--init` / `--check` | environment tests in `test_main_flow.py` | run commands manually |
| learning loop | `test_main_flow.py` + `test_engine_navigation.py` | manual demo or file smoke test |
| engine state transitions | `test_engine_navigation.py` | full `pytest tests/unit/` |
| router/review intent | `test_router.py` | manual “复习一下 xxx” flow |
| translator/prompt parsing | `test_translator.py` | integration test with real LLM if API key is available |
| dependencies/config | `test_config.py`, `python main.py --check` | GitHub Actions |
| release | full unit tests + CI + artifact hygiene | fresh clone install smoke test |

If the task changes behavior across modules, verify each touched boundary.

Example:

```text
Changed review mode output in src/cli/review.py and src/core/engine.py
-> run test_engine_navigation.py
-> run review-related test_main_flow.py tests
-> run python main.py --check
```

---

## Preflight Checks

Before running heavy tests, check the project shape.

Recommended commands:

```bash
git status --short --branch
git diff --check
python main.py --check
```

What to look for:

- There are no accidental unrelated file edits.
- There are no trailing whitespace errors.
- `.env` is not staged.
- `logs/`, `data/users/`, `__pycache__/`, `.pytest_cache/` are not staged.
- `python main.py --check` reports API key, config, dependencies, and demo material status.

If `git status` warns about permission-denied temporary directories, do not treat that as a code failure. Identify whether those directories were created by local test attempts.

---

## Test Commands

### Full Unit Suite

Use before release or after behavior changes:

```bash
pytest tests/unit/
```

Equivalent explicit Python form:

```bash
python -m pytest tests/unit/
```

### Focused Unit Tests

Use when the change is narrow:

```bash
pytest tests/unit/test_main_flow.py
pytest tests/unit/test_engine_navigation.py
pytest tests/unit/test_router.py
pytest tests/unit/test_translator.py
pytest tests/unit/test_file_loader.py
pytest tests/unit/test_config.py
pytest tests/unit/test_storage.py
```

### Syntax Checks

Use after moving code across modules:

```bash
python -m py_compile main.py src/cli/*.py src/core/*.py src/utils/*.py src/llm/*.py models/*.py
```

On Windows PowerShell, wildcard behavior can vary. If needed, compile explicit files:

```powershell
python -m py_compile main.py src\cli\display.py src\cli\environment.py src\cli\review.py src\core\engine.py
```

### Manual CLI Smoke Checks

Use when changing user-facing CLI behavior:

```bash
python main.py --check
python main.py --demo
python main.py --file tests/integration/sample_article.md
```

The `--demo` and `--file` flows need a valid API key because they call the LLM.

If no API key is available, run `--check` and unit tests, then clearly state that LLM smoke testing was not run.

---

## Behavior Verification

Use this section when changing runtime behavior.

### New Topic

Verify:

- A topic can start from `--file`.
- A topic can start from `/load <path>` in new-topic input.
- A topic can start from short pasted text.
- Empty input does not create a broken topic.
- Demo mode uses `samples/demo_article.md`.

Expected evidence:

```text
Material loaded -> material analyzed -> 3-7 chunks -> first question displayed.
```

### Learning Loop

Verify:

- The current chunk is taught before asking.
- The first user answer is confirmed before judgment.
- Correct answer advances.
- Correct answer on final chunk completes and shows summary.
- Wrong answer gives a progressive hint and keeps the user on the same chunk.
- `/direct` shows the answer and marks `needs_review`.
- `/skip` marks `needs_review` and advances.
- `/back` returns to the previous chunk without losing state.
- `/jump N` moves to the selected chunk.
- `/progress` displays mastered, needs review, not started, attempts, and wrong count.
- `/list` displays all chunks.
- `/review` displays weak chunks.
- `/exit` saves progress.

Recommended tests:

```bash
pytest tests/unit/test_main_flow.py
pytest tests/unit/test_engine_navigation.py
```

### Resume Flow

Verify:

- Saved topic state loads.
- Conversation history loads when present.
- Resume does not call `start_topic()` before the learning loop.
- Completed topics show summary instead of restarting.
- Topic list shows readable title, source, summary, and progress.

Recommended test:

```bash
pytest tests/unit/test_main_flow.py -k Resume
```

### Review Flow

Verify:

- “复习一下 xxx” is recognized as review intent.
- Matching uses historical topic metadata.
- Review mode prioritizes weak chunks.
- Review mode asks directly, without normal teaching.
- Correct review answer can move a chunk back to mastered.
- `/direct` and `/skip` keep the chunk as `needs_review`.
- Review summary reports answered, correct, direct, skipped, and remaining weak items.
- `last_reviewed_at` updates after review.

Recommended tests:

```bash
pytest tests/unit/test_router.py
pytest tests/unit/test_engine_navigation.py -k review
pytest tests/unit/test_main_flow.py -k Review
```

### Material Append

Verify:

- `/load <path>` during learning appends chunks to the current topic.
- Current question is not interrupted.
- `total_chunks` updates.
- New chunk titles are displayed.
- Progress is saved after append.

Recommended test:

```bash
pytest tests/unit/test_main_flow.py -k load
```

---

## Skill Documentation Verification

Use this section when editing:

- `skills/heuristic-teacher/SKILL.md`
- `skills/heuristic-teacher/references/*.md`

### Frontmatter

For `SKILL.md`, verify the YAML frontmatter contains at least:

```yaml
name:
description:
```

The description must clearly say when the Skill should trigger.

Good description qualities:

- Mentions learning material.
- Mentions explain-question-feedback loop.
- Mentions Teacher-skill CLI if this Skill supports project work.
- Mentions review or verification if those are core use cases.

Avoid vague descriptions like:

```text
Helps with teaching.
```

### Body Structure

Verify `SKILL.md` explains:

- when to use
- when not to use
- role of the agent
- main learning workflow
- review workflow
- project optimization workflow
- command behavior
- state meanings
- when to read references
- minimum completion standard

### Reference Files

Reference files should be loaded only when needed.

Verify:

- `SKILL.md` links to each reference file.
- Each reference file has a clear purpose.
- Reference files do not duplicate the entire `SKILL.md`.
- Long reference files include a table of contents.
- File paths mentioned in references match the real repo.

### Markdown Checks

Run:

```bash
git diff --check -- skills/heuristic-teacher/SKILL.md
git diff --check -- skills/heuristic-teacher/references/teaching-loop.md
git diff --check -- skills/heuristic-teacher/references/verification.md
```

Also read the changed file once from top to bottom to catch:

- broken headings
- unclear instructions
- outdated paths
- contradiction with `SKILL.md`
- instructions that tell the agent to do too much at once

---

## Prompt Verification

Use this section when editing files under `prompts/`.

### Analyzer Prompt

Verify output contains:

- valid JSON
- readable topic title
- short summary
- 3-7 chunks
- each chunk has title, content, question, correct answer

Failure signs:

- chunks are just paragraphs
- no correct answer
- question is trivia
- output has Markdown around JSON when parser cannot handle it

### Teach Prompt

Verify output:

- teaches one chunk
- asks one question
- does not judge
- does not reveal the full answer before the user answers
- returns `response_type="question"`

### Judge Prompt

Verify output:

- judges semantic correctness
- includes feedback
- includes hint level
- includes next action
- does not introduce a new chunk
- does not reveal full answer too early

### Review Prompt

Verify output:

- is shorter than normal teaching feedback
- checks memory instead of reteaching
- handles direct answer and skip behavior
- keeps weak chunks in review when needed

Recommended parser tests:

```bash
pytest tests/unit/test_translator.py
```

---

## Storage Verification

Use this section when changing persistence, profiles, resume, review history, or topic metadata.

Verify these files are created or updated at runtime:

```text
data/users/{user_id}/topics/{topic_id}/state.json
data/users/{user_id}/topics/{topic_id}/history.json
data/users/{user_id}/profile.json
```

Expected behavior:

- `state.json` saves current topic state.
- `history.json` saves conversation messages when messages exist.
- `profile.json` saves onboarding level and learned topic history.
- Completed topics are archived in `history_topics`.
- Review completion updates `last_reviewed_at`.

Do not commit runtime user data.

Before publishing, verify these are absent from staged files:

```bash
git status --short
```

Forbidden in release commits:

```text
.env
logs/
data/users/
__pycache__/
.pytest_cache/
debug_output.txt
```

---

## Release Verification

Use this section before sharing the repository or tagging a release.

### Required Checks

Run or confirm:

```bash
pytest tests/unit/
python main.py --check
git diff --check
```

Confirm GitHub Actions is green.

Confirm docs are current:

- `README.md` is an entry page, not a giant manual.
- `docs/install/README.md` explains installation and configuration.
- `docs/development/status.md` reflects the current stage.
- `docs/development/release-checklist.md` has accurate checkboxes.
- `docs/development/changelog.md` records important changes.
- `docs/product/roadmap.md` reflects what is complete and next.

Confirm Skill structure:

```text
skills/heuristic-teacher/
  SKILL.md
  references/
    teaching-loop.md
    verification.md
```

Confirm dependency files:

- `requirements.txt` includes runtime dependencies used by tests and app code.
- `.env.example` contains placeholders only.
- `config.yaml` contains model/config defaults, not secrets.

### Release Decision

Use this decision table:

| Condition | Decision |
|---|---|
| Unit tests pass locally and CI passes | Ready to publish |
| Local tests blocked but CI passes | Can publish if blocker is environment-specific and documented |
| CI fails | Do not publish |
| `.env` or user data staged | Do not publish |
| README/docs point to wrong paths | Do not publish |
| Skill lacks clear trigger description | Do not publish as installable Skill |

---

## GitHub Actions Verification

The repository uses GitHub Actions for unit tests.

Workflow path:

```text
.github/workflows/tests.yml
```

Use GitHub Actions to confirm:

- dependencies install from `requirements.txt`
- `pytest tests/unit/` runs in a clean environment
- tests are not relying on local hidden state

If CI fails:

1. Read the failing job name.
2. Read the first real traceback.
3. Identify whether failure is dependency, import, assertion, or environment.
4. Fix the smallest related cause.
5. Re-run CI.

Do not force-push blindly just to make CI rerun. Understand the failure first.

---

## Windows and Local Environment Issues

This project is often run on Windows PowerShell.

### Common Issue: pytest Temporary Directory Permission

Symptom:

```text
PermissionError: [WinError 5] 拒绝访问
pytest-of-Administrator
tmp_path
```

Meaning:

```text
Tests using tmp_path cannot create or clean temporary directories in the current execution environment.
```

This is usually an environment permission issue, not a business logic failure.

Correct response:

- Say which tests were blocked.
- Run focused tests that do not require `tmp_path` if useful.
- Ask the user to run full pytest in normal PowerShell, or rely on GitHub Actions.

Useful command for the user:

```powershell
cd C:\Users\Administrator\Desktop\Teacher-skill\Teacher-skill
python -m pytest tests\unit\
```

If test temp directories were created and are safe to remove, tell the user what they are before suggesting deletion.

Do not delete directories recursively unless you are certain they are test artifacts and the path is inside the workspace.

### Common Issue: Missing Dependency

Symptom:

```text
ModuleNotFoundError: No module named 'yaml'
```

Fix:

```bash
python -m pip install -r requirements.txt
```

Then ensure the dependency exists in `requirements.txt`.

### Common Issue: Network Blocked During Install

If `pip install` fails due to sandbox or network restrictions:

- Report the network blocker.
- Check whether another Python environment already has dependencies.
- Ask the user to run install locally.
- Do not claim dependencies were installed.

---

## Failure Triage

Use this order when something fails:

### 1. Import or Dependency Failure

Examples:

```text
ModuleNotFoundError
ImportError
```

Check:

- Is the dependency in `requirements.txt`?
- Is the correct Python interpreter being used?
- Does CI install the dependency?

### 2. Syntax Failure

Examples:

```text
SyntaxError
IndentationError
```

Run:

```bash
python -m py_compile <changed files>
```

### 3. Assertion Failure

Examples:

```text
assert expected == actual
```

Check:

- Did behavior intentionally change?
- Should the code be fixed or the test updated?
- Is the test protecting a real user-facing behavior?

### 4. Prompt Parsing Failure

Examples:

```text
JSONDecodeError
missing response_type
missing correct_answer
```

Check:

- Did the prompt stop requiring JSON?
- Did translator fallback break?
- Does the LLM response contain extra Markdown or thinking text?

### 5. Environment Failure

Examples:

```text
PermissionError
network timeout
API key missing
rate limit
```

Do not rewrite application logic unless the failure proves a code problem.

---

## Evidence to Report

After verification, report evidence clearly.

Good final report:

```text
Changed:
- skills/heuristic-teacher/references/verification.md

Verified:
- git diff --check -- skills/heuristic-teacher/references/verification.md

Notes:
- Documentation-only change; no runtime tests required.
```

For code changes:

```text
Verified:
- python -m py_compile main.py src/cli/review.py
- pytest tests/unit/test_main_flow.py -k Review
- python main.py --check

Not run:
- Full pytest, blocked by Windows tmp_path permission in this Codex environment.
```

Bad final report:

```text
All good.
```

It does not say what was checked.

---

## Minimum Acceptance Checklist

Use this checklist before saying verification is complete.

### For Documentation-Only Changes

- The changed Markdown file is readable.
- It has a clear purpose.
- It does not contradict `SKILL.md`.
- It uses accurate project paths.
- `git diff --check` passes for the changed file.

### For Skill Release

- `SKILL.md` has clear frontmatter.
- `SKILL.md` tells the agent when to use and when not to use the Skill.
- References are linked from `SKILL.md`.
- References contain details, not unrelated project history.
- The Skill folder contains only files useful to the agent.

### For Runtime Changes

- Relevant focused tests pass.
- `python main.py --check` passes or gives expected missing-config guidance.
- State changes are saved correctly.
- Commands are not judged as normal answers.
- Direct answers and skips mark `needs_review`.
- Review flow updates history metadata.

### For Release

- `pytest tests/unit/` passes locally or in CI.
- GitHub Actions is green.
- `.env` and runtime user data are not committed.
- README and docs paths are current.
- Changelog/status/checklist reflect the release state.

Verification is complete only when the evidence matches the risk of the change.
