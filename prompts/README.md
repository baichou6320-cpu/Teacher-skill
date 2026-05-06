# Prompts

Teacher-skill uses split prompts by default.

| Path | Purpose |
|---|---|
| `_base.md` | Shared protocol, constraints, and output contract |
| `_persona.md` | Default teaching voice and interaction style |
| `system/00_onboarding.md` | User level detection |
| `system/01_analyzer.md` | Material analysis and knowledge chunking |
| `system/02_teach.md` | Teaching and validation question generation |
| `system/03_judge.md` | Answer judgment and progressive hints |
| `system/04_review.md` | Review-mode judgment and short feedback |
| `legacy/` | Old merged prompt files kept for backward compatibility |

The default `config.yaml` value is:

```yaml
teaching:
  prompt_mode: "split"
```

Use `prompt_mode: "merged"` only when you intentionally want to exercise the
legacy prompt path.

