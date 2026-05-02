# Install Guide

This guide gets Teacher-skill running as a local CLI tool.

## Requirements

- Python 3.11+
- Git
- An Anthropic-compatible API key

## Clone

```bash
git clone https://github.com/baichou6320-cpu/Teacher-skill.git
cd Teacher-skill
```

## Create Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure API

Copy the example environment file:

```bash
cp .env.example .env
```

Set your API key:

```text
ANTHROPIC_API_KEY=your_api_key_here
```

Optional custom Anthropic-compatible base URL:

```text
ANTHROPIC_BASE_URL=https://api.moonshot.cn/anthropic
```

Model and generation settings live in `config.yaml`, not `.env`:

```yaml
llm:
  model_id: "claude-sonnet-4-20250514"
```

For Kimi/Moonshot-style compatible APIs, set both:

```text
# .env
ANTHROPIC_BASE_URL=https://api.moonshot.cn/anthropic
```

```yaml
# config.yaml
llm:
  model_id: "kimi-k2.5"
```

## Run

Recommended file-based mode:

```bash
python main.py --file tests/integration/sample_article.md
```

Interactive mode:

```bash
python main.py
```

Supported file types:

- `.md`
- `.txt`
- `.pdf`

In interactive mode, use `/load <path>` to load a file. During learning, the same
command appends the file as additional knowledge points in the current topic.

Useful learning commands:

- `/progress` shows progress, mastered items, review items, and answer stats.
- `/list` shows all knowledge points.
- `/review` shows weak or review-needed knowledge points.
- `/skip` skips the current point and marks it as needing review.
- `/back` returns to the previous point.
- `/jump N` jumps to a specific point, for example `/jump 3`.

## Verify

Unit tests do not need an API key:

```bash
pytest tests/unit/
```

Integration tests need a real API key:

```bash
python tests/integration/test_e2e.py
python tests/integration/test_tutoring_loop.py
```

## Data and Logs

Runtime data is written under:

- `data/users/`
- `logs/`

These paths are ignored by git and should not be published.
