# Scripts

This directory contains manual helper scripts. The product entry point remains
`main.py`; scripts here are for demos, smoke checks, and debugging.

| Directory | Purpose | Needs API Key |
|---|---|---|
| `smoke/` | Manual end-to-end checks against a real LLM | Yes |
| `dev/` | Debug helpers for prompt and parser development | Yes |

Common commands:

```bash
python scripts/smoke/llm_e2e_check.py
python scripts/smoke/tutoring_loop_check.py
```

For the fixed offline demo, use the root-level script:

```bash
python demo_full_loop.py
```
