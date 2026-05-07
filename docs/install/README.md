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

## Initialize Project

Prepare local runtime files:

```bash
python main.py --init
```

This command:

- copies `.env.example` to `.env` if `.env` does not exist
- keeps an existing `.env` unchanged
- creates the configured data and logs directories
- checks that the built-in demo material exists

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

Open `.env` and set your API key:

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

## Check Setup

After installing dependencies and editing `.env`, run:

```bash
python main.py --check
```

The check verifies:

- Python version
- `.env` presence
- `ANTHROPIC_API_KEY`
- `config.yaml`
- runtime dependencies
- optional test dependencies
- built-in demo material

If a required item is missing, fix the red item first. Optional test dependencies
only affect local test commands, not normal learning.

## Run

Local web mode:

```bash
python main.py --web
```

This starts a website on `http://127.0.0.1:8765/` and opens your browser. It is a
local-only server, not a public deployment. The page calls the same local
`/api/analyze` endpoint used by the Python bridge.

On first run, `--web` checks the environment. If the API key or model config is
missing, it starts the setup wizard first and then continues to the local
website after setup succeeds.

Quick demo mode:

```bash
python main.py --demo
```

`--demo` uses the built-in article `samples/demo_article.md`, so you do not need
to prepare your own learning material for the first run. It still needs a valid
LLM API key.

Recommended file-based mode:

```bash
python main.py --file samples/sample_article.md
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
- `/history` shows archived topics after completion.
- `/skip` skips the current point and marks it as needing review.
- `/back` returns to the previous point.
- `/jump N` jumps to a specific point, for example `/jump 3`.

## Verify

Unit tests do not need an API key:

```bash
pytest tests/unit/
```

LLM smoke scripts need a real API key:

```bash
python scripts/smoke/llm_e2e_check.py
python scripts/smoke/tutoring_loop_check.py
```

## Data and Logs

Runtime data is written under:

- `data/users/`
- `logs/`

These paths are ignored by git and should not be published.
