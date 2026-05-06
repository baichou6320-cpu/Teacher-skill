# Tests

The tracked test suite is intentionally focused on unit tests that do not need
an API key.

```bash
pytest tests/unit/
```

Manual LLM checks live outside this directory:

```bash
python scripts/smoke/llm_e2e_check.py
python scripts/smoke/tutoring_loop_check.py
```
