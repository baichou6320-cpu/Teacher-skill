# Verification Reference

Use this checklist when changing or validating the Teacher-skill workflow.

## Functional Checks

- A new topic can be created from pasted text.
- A new topic can be created from a supported file.
- A saved topic can be resumed without repeating the same opening message twice.
- The final chunk completes the loop and shows the summary.
- `/direct` advances and marks the current chunk as `needs_review`.
- `/progress` reports the current chunk index and total chunks.
- `/exit` saves progress before ending the session.

## Prompt Checks

- Analyzer output is valid JSON.
- Analyzer output contains 3-7 chunks.
- Teach output uses `response_type: "question"`.
- Judge output includes `is_correct`, `feedback`, `hint_level`, and `action`.
- Hint levels below 4 do not reveal the complete correct answer.

## Storage Checks

- `state.json` is saved for the topic.
- `history.json` is saved when messages exist.
- User profile is saved after onboarding.
- User data remains under `data/users/` and should not be committed.

## Release Checks

- Unit tests pass with `pytest tests/unit/`.
- `.env`, `logs/`, `data/users/`, `__pycache__/`, and `.pytest_cache/` are not included in releases.
- README links point to the current document paths.
- Product notes live under `docs/product/`.
- Development notes live under `docs/development/`.
- Learning notes live under `docs/learning-notes/`.
- Install notes live under `docs/install/`.
