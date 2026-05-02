# Release Checklist

Use this checklist before publishing a GitHub release or sharing a packaged copy.

## Required

- [x] `pytest tests/unit/` passes locally after adding main.py flow tests.
- [ ] GitHub Actions unit-test workflow passes.
- [x] `README.md` links point to current paths.
- [x] `docs/development/status.md` reflects the current release state.
- [ ] `docs/product/roadmap.md` reflects what is complete and what is next.
- [x] `docs/development/changelog.md` has a release entry.
- [x] `skills/heuristic-teacher/SKILL.md` describes the stable Agent Skill workflow.
- [x] `skills/heuristic-teacher/references/` contains supporting verification notes.
- [x] `LICENSE` exists.
- [x] `.env.example` exists and contains placeholders only.
- [x] `requirements.txt` includes runtime dependencies needed by tests, including `PyYAML`.

## Do Not Publish

Confirm these files or directories are absent from the release artifact and not committed:

- [x] `.env`
- [x] `logs/`
- [x] `data/users/`
- [x] `__pycache__/`
- [x] `.pytest_cache/`
- [x] `debug_output.txt`
- [x] local editor or host settings that contain personal paths or permissions

## Manual Smoke Test

Run these after installing dependencies:

```bash
pytest tests/unit/
python main.py
```

For file loading:

```bash
python main.py --file tests/integration/sample_article.md
```

## Release Notes Template

```markdown
## vX.Y.Z - YYYY-MM-DD

### Added

### Changed

### Fixed

### Verification

- Unit tests:
- Manual CLI smoke test:
```
