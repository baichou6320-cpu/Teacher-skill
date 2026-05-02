# Teacher-skill

[![Tests](https://github.com/baichou6320-cpu/Teacher-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/baichou6320-cpu/Teacher-skill/actions/workflows/tests.yml)

启发式数字助教 CLI，通过「讲解 -> 提问 -> 反馈」闭环帮助用户避免“理解幻觉”。

```text
学习材料 -> 知识卡片 -> 逐个讲解 -> 提问验证 -> 判卷反馈
```

## Quick Start

需要 Python 3.11+。

```bash
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY

pip install -r requirements.txt
python main.py
```

从文件加载材料：

```bash
python main.py --file article.md
```

模型和生成参数在 `config.yaml` 中配置；`.env` 只用于 API Key 和可选的 `ANTHROPIC_BASE_URL`。

## Commands

- `/help` — 查看帮助
- `/progress` — 查看当前进度
- `/direct` — 直接查看答案，并标记当前知识点为待巩固
- `/exit` — 保存进度并退出

## Agent Skill

标准 Agent Skill 定义在：

- [skills/heuristic-teacher/SKILL.md](skills/heuristic-teacher/SKILL.md)

这个文件只描述 Agent 执行启发式教学时必须遵守的工作流。项目说明、PRD、路线图和学习笔记都放在 `docs/` 中，避免污染 Skill 核心。

## Documentation

- [安装和配置](docs/install/README.md)
- [项目总览](docs/product/project-overview.md)
- [PRD](docs/product/PRD.md)
- [路线图](docs/product/roadmap.md)
- [当前状态](docs/development/status.md)
- [发布检查清单](docs/development/release-checklist.md)
- [变更日志](docs/development/changelog.md)
- [复习模式设计](docs/product/review-mode.md)
- [学习笔记](docs/learning-notes/README.md)

## Verification

单元测试无需 API Key：

```bash
pytest tests/unit/
```

集成测试需要配置真实 LLM API Key：

```bash
python tests/integration/test_e2e.py
python tests/integration/test_tutoring_loop.py
```
