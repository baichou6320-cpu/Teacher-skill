# Teacher-skill

[![Tests](https://github.com/baichou6320-cpu/Teacher-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/baichou6320-cpu/Teacher-skill/actions/workflows/tests.yml)

Teacher-skill 是一个启发式数字助教 CLI。它把学习材料拆成知识卡片，通过「讲解 -> 提问 -> 判卷 -> 渐进提示」的闭环，帮助用户避免“看懂了但说不出来”的理解幻觉。

```text
学习材料 -> 知识卡片 -> 逐个讲解 -> 提问验证 -> 判卷反馈 -> 复习巩固
```

## 项目状态

| 项目 | 状态 |
|------|------|
| 核心教学闭环 | 可用 |
| 项目初始化 | 支持 `python main.py --init` 创建本地配置和运行目录 |
| 启动检查 | 支持 `python main.py --check` 定位配置问题 |
| Demo 体验 | 支持 `python main.py --demo` 使用内置材料 |
| 文件输入 | 支持 `.md` / `.txt` / `.pdf` |
| 进度保存 | 支持历史 topic 恢复 |
| 历史归档 | 完成主题后自动写入 profile，可用 `/history` 查看 |
| 单元测试 | GitHub Actions 已接入 |
| 当前定位 | 本地 CLI 学习工具，适合开发者和愿意使用命令行的学习者 |

## 适合谁

- 正在自学 AI、技术文档、课程资料的人
- 读完资料后容易“感觉懂了，但无法复述”的人
- 想把长文档拆成小知识点逐个验证的人
- 想学习如何设计 Agent Skill / CLI 教学产品的人

## 快速开始

需要 Python 3.11+。

```bash
git clone https://github.com/baichou6320-cpu/Teacher-skill.git
cd Teacher-skill

python main.py --init
# 编辑 .env，填入 ANTHROPIC_API_KEY

python -m pip install -r requirements.txt
python main.py --check
python main.py --demo
```

`--init` 会创建 `.env`、`data/` 和 `logs/`，并且不会覆盖已有 `.env`。

`--check` 会检查 API Key、`config.yaml`、运行依赖和内置示例材料。它适合在第一次运行或报错时快速定位问题。

`--demo` 会使用内置短文《番茄工作法入门》，适合第一次体验。正式学习时推荐使用 `--file` 从文件直接开始：

```bash
python main.py --file article.md
```

也可以进入交互模式后使用 `/load` 加载材料：

```bash
python main.py
```

模型和生成参数在 `config.yaml` 中配置；`.env` 只用于 API Key 和可选的 `ANTHROPIC_BASE_URL`。更详细的安装步骤见 [安装和配置](docs/install/README.md)。

## 使用体验

学习开始后，系统会自动完成这些事：

1. 读取你的学习材料
2. 拆分成多个知识卡片
3. 逐个讲解知识点
4. 提问验证你是否真的理解
5. 根据回答给出判卷反馈或渐进提示
6. 保存进度，方便下次继续
7. 学完后归档到历史学习记录，为后续复习做准备

普通回答不会立刻判卷，会先进入提交确认：

| 输入 | 行为 |
|------|------|
| Enter | 提交当前回答 |
| `/edit` | 修改回答 |
| `/cancel` | 取消本次提交 |

答错时系统会显示温和提示面板，并标明当前提示层级，例如「第 2/4 层：生活类比」。

## 常用命令

| 命令 | 作用 |
|------|------|
| `/help` | 查看帮助 |
| `/progress` | 查看当前进度、掌握数、待巩固数和答题统计 |
| `/list` | 查看全部知识点 |
| `/review` | 查看待巩固知识点 |
| `/history` | 查看已归档的历史学习主题 |
| `/skip` | 跳过当前知识点，并标记为待巩固 |
| `/back` | 回到上一个知识点 |
| `/jump N` | 跳到第 N 个知识点，例如 `/jump 3` |
| `/direct` | 直接查看答案，并标记当前知识点为待巩固 |
| `/load <路径>` | 加载文件；学习中使用会追加为新的知识点 |
| `/exit` | 保存进度并退出 |

在主题选择时，也可以直接输入自然语言复习请求，例如“复习一下 Transformer”。系统会匹配历史主题，并进入复习模式：跳过讲解，优先提问待巩固、答错过或用过提示的知识点；复习结束后会输出本轮统计和仍待巩固列表。

## 项目结构

```text
Teacher-skill/
├── main.py                         # CLI 入口
├── config.yaml                     # 模型与生成参数
├── requirements.txt                # Python 依赖
├── models/                         # 协议和状态模型
├── src/                            # 核心引擎、LLM、工具模块
├── prompts/                        # 分层 Prompt
├── samples/                        # 内置 demo 学习材料
├── skills/heuristic-teacher/       # 标准 Agent Skill
├── tests/                          # 单元测试和集成测试
└── docs/                           # 产品、开发、安装和学习笔记
```

## Agent Skill

标准 Skill 定义在 [skills/heuristic-teacher/SKILL.md](skills/heuristic-teacher/SKILL.md)。

这个文件只保留 Agent 执行启发式教学时必须遵守的工作流。项目说明、PRD、路线图和学习笔记都放在 `docs/` 中，避免污染 Skill 核心。

## 文档入口

| 文档 | 说明 |
|------|------|
| [安装和配置](docs/install/README.md) | 从零运行项目 |
| [项目总览](docs/product/project-overview.md) | 产品定位、机制和模块说明 |
| [PRD](docs/product/PRD.md) | 产品需求文档 |
| [路线图](docs/product/roadmap.md) | 后续开发计划 |
| [当前状态](docs/development/status.md) | 当前可用能力和待办 |
| [发布检查清单](docs/development/release-checklist.md) | 发布前检查项 |
| [变更日志](docs/development/changelog.md) | 重要改动记录 |
| [学习笔记](docs/learning-notes/README.md) | 项目学习沉淀 |

## 验证

单元测试无需 API Key：

```bash
pytest tests/unit/
```

集成测试需要配置真实 LLM API Key：

```bash
python tests/integration/test_e2e.py
python tests/integration/test_tutoring_loop.py
```

## License

MIT
