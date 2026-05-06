# Teacher-skill

<div align="center">
  <img src="skills/heuristic-teacher/assets/heuristic-teacher.svg" alt="Teacher-skill visual identity" width="720">

  <p><strong>一个启发式数字助教 CLI，把阅读材料变成主动回忆、提问验证和复习巩固。</strong></p>
  <p>学习材料 -> 提问验证 -> 判卷反馈 -> 复习巩固</p>

  <p>
    <a href="https://github.com/baichou6320-cpu/Teacher-skill/actions/workflows/tests.yml">
      <img alt="Tests" src="https://github.com/baichou6320-cpu/Teacher-skill/actions/workflows/tests.yml/badge.svg">
    </a>
    <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
    <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-green">
    <img alt="Interface CLI" src="https://img.shields.io/badge/Interface-CLI-0F766E">
  </p>
</div>

Teacher-skill 不是一个更快的总结器。它的目标是解决学习里的“理解幻觉”：看完解释时感觉懂了，但一合上材料就无法复述、无法判断边界，也不能把概念用到真实问题里。

它会把材料拆成知识卡片，并强制进入一个小闭环：

```text
学习材料 -> 知识卡片 -> 讲解 -> 提问 -> 用户作答 -> 判卷反馈 -> 复习巩固
```

## 你可以用它做什么

| 场景 | Teacher-skill 怎么帮你 |
|---|---|
| 学技术文章、课程笔记、论文摘要 | 拆成 3-7 个知识点，逐个讲解和提问 |
| 检查自己是不是真的懂 | 通过主动回答验证理解，而不是只读解释 |
| 答错后继续推进 | 先给线索、类比、半解析，再逐步增加提示 |
| 时间紧时查答案 | `/direct` 直接看答案，并自动标记为待巩固 |
| 回顾旧主题 | 用“复习一下 xxx”匹配历史主题，优先检查薄弱点 |
| 构建 Agent Skill | 项目内置标准 Skill 结构，可作为学习样例 |

## 当前状态

| 模块 | 状态 |
|---|---|
| 核心教学闭环 | 可用 |
| CLI 初始化 | `python main.py --init` |
| 环境检查 | `python main.py --check` |
| 固定 3 分钟演示 | `python demo_full_loop.py` |
| Demo 体验 | `python main.py --demo` |
| 文件输入 | `.md` / `.txt` / `.pdf` |
| 学习控制命令 | `/progress`、`/list`、`/skip`、`/back`、`/jump`、`/direct` |
| 历史归档 | 主题完成后写入 `profile.history_topics` |
| 复习模式 | 基础版可用，支持自然语言匹配历史主题 |
| 测试 | 单元测试接入 GitHub Actions |
| 产品定位 | 本地 CLI 学习工具，适合开发者和愿意使用命令行的学习者 |

## 快速开始

需要 Python 3.11+ 和 Git。固定 3 分钟演示不依赖 API；真实学习流程需要一个 LLM API Key（支持 Anthropic / Kimi / DeepSeek 等）。

```bash
git clone https://github.com/baichou6320-cpu/Teacher-skill.git
cd Teacher-skill

python -m pip install -r requirements.txt
python main.py
```

首次运行 `python main.py` 时，系统会自动检测环境。如果缺少配置，会引导你进入交互式配置向导：

1. **选择模型服务商**（Claude / Kimi / DeepSeek / 自定义接口）
2. **粘贴 API Key**
3. 自动写入 `.env` 和 `config.yaml`

配置完成后即可开始学习。

> 无 API Key 时也可以先运行 `python main.py --check` 检查环境，或 `python demo_full_loop.py` 体验固定演示。

## 四种启动方式

### 1. 直接运行（推荐）

自动检测环境，缺失配置时会引导你完成 setup。

```bash
python main.py
```

### 2. 固定 3 分钟演示

不依赖 API、不等待现场输入，适合展示。

```bash
python demo_full_loop.py
```

配套话术见 [`docs/demo/three-minute-demo.md`](docs/demo/three-minute-demo.md)。

### 3. 从文件开始学习

```bash
python main.py --file article.md
```

支持 `.md` / `.txt` / `.pdf`。

### 4. 手动配置向导

如果你希望主动运行配置向导（选择模型、粘贴 API Key）：

```bash
python main.py --setup
```

配置完成后，后续直接运行 `python main.py` 即可。

在交互模式中可以输入：

```text
/load path/to/article.md
```

长材料推荐先保存成文件，再用 `--file` 或 `/load` 加载。

## 学习流程

```text
Step 1 读取材料
Step 2 分析并拆成知识卡片
Step 3 讲解当前知识点
Step 4 提问验证
Step 5 用户作答
Step 6 判卷并反馈
Step 7 保存进度
Step 8 完成后归档，等待后续复习
```

答错时不会立刻公布完整答案，而是使用渐进提示：

| 层级 | 提示方式 | 目标 |
|---|---|---|
| 1 | 线索提示 | 给方向，不替你回答 |
| 2 | 生活类比 | 换一个熟悉场景理解 |
| 3 | 半解析 | 给部分推理链 |
| 4 | 关键词或部分答案 | 帮你越过卡点，并标记待巩固 |

普通回答会先进入提交确认：

| 输入 | 行为 |
|---|---|
| Enter | 提交当前回答 |
| `/edit` | 修改回答 |
| `/cancel` | 取消本次提交 |

## 命令速查

| 命令 | 作用 |
|---|---|
| `/help` | 查看帮助 |
| `/progress` | 查看当前进度、掌握数、待巩固数和答题统计 |
| `/list` | 查看全部知识点 |
| `/review` | 查看当前主题中需要巩固的知识点 |
| `/history` | 查看已归档的历史学习主题 |
| `/skip` | 跳过当前知识点，并标记为待巩固 |
| `/back` | 回到上一个知识点 |
| `/jump N` | 跳到第 N 个知识点，例如 `/jump 3` |
| `/direct` | 直接查看答案，并标记当前知识点为待巩固 |
| `/load <路径>` | 加载文件；学习中使用会追加为新的知识点 |
| `/exit` | 保存进度并退出 |

## 复习模式

完成主题后，Teacher-skill 会把学习记录写入用户档案。下次进入交互模式时，可以直接说：

```text
复习一下 Transformer
```

系统会从历史主题中匹配最相关的记录，并进入复习模式：

```text
历史主题 -> 薄弱点排序 -> 直接提问 -> 短反馈 -> 更新复习记录
```

复习模式会优先检查：

- `needs_review` 的知识点
- 答错过的知识点
- 使用过提示的知识点
- 尚未完成的知识点

复习结束后会输出本轮统计，并更新 `last_reviewed_at`、掌握数和待巩固数。

## 项目结构

```text
Teacher-skill/
├── main.py                         # CLI 入口和应用编排
├── config.yaml                     # 模型与生成参数
├── requirements.txt                # Python 依赖
├── models/                         # 协议、状态、用户档案模型
├── src/
│   ├── cli/                        # 启动检查、展示、复习 CLI 流程
│   ├── core/                       # 教学状态机、记忆、奖励、路由
│   ├── llm/                        # LLM 客户端、异常、响应解析
│   └── utils/                      # 配置、文件加载、日志、存储
├── prompts/                        # 当前 split Prompt，legacy/ 为旧版兼容
├── samples/                        # 内置 demo 和示例学习材料
├── skills/heuristic-teacher/       # 标准 Agent Skill
├── tests/unit/                     # 无需 API Key 的单元测试
├── scripts/                        # 手动烟测和开发调试脚本
└── docs/                           # 产品、安装、演示、开发和归档文档
```

## 架构概览

| 模块 | 文件 | 职责 |
|---|---|---|
| CLI 应用 | `main.py` | 参数解析、用户流程编排、进度保存 |
| 启动检查 | `src/cli/environment.py` | 初始化、依赖检查、配置检查 |
| 控制台展示 | `src/cli/display.py` | Rich 表格、反馈面板、学习总结 |
| 复习 CLI | `src/cli/review.py` | 复习循环、复习统计、历史更新 |
| 教学引擎 | `src/core/engine.py` | 状态机、讲解、判卷、跳转、复习队列 |
| 意图路由 | `src/core/router.py` | 识别“复习一下 xxx”并匹配历史主题 |
| LLM 客户端 | `src/llm/client.py` | Anthropic 兼容调用、重试、错误分类 |
| 响应解析 | `src/llm/translator.py` | JSON 提取、判卷解析、文本兜底 |
| 文件加载 | `src/utils/file_loader.py` | `.md` / `.txt` / `.pdf` 内容读取 |
| 存储 | `src/utils/storage.py` | `state.json`、`history.json`、`profile.json` |

## Agent Skill

标准 Skill 定义在：

```text
skills/heuristic-teacher/SKILL.md
```

它描述了 Agent 如何执行启发式教学：拆知识点、一次只教一个点、提问验证、语义判卷、渐进提示、复习薄弱点。

支持文件：

| 文件 | 用途 |
|---|---|
| `skills/heuristic-teacher/SKILL.md` | Skill 主工作流 |
| `skills/heuristic-teacher/references/teaching-loop.md` | 教学闭环细节 |
| `skills/heuristic-teacher/references/verification.md` | 发布和验证参考 |
| `skills/heuristic-teacher/assets/` | Skill 视觉资产 |

## 验证

单元测试不需要 API Key：

```bash
pytest tests/unit/
```

真实 LLM 烟测需要 API Key：

```bash
python scripts/smoke/llm_e2e_check.py
python scripts/smoke/tutoring_loop_check.py
```

发布前建议至少跑：

```bash
python main.py --check
pytest tests/unit/
```

## 常见问题

### `python main.py --check` 提示缺依赖

重新安装依赖：

```bash
python -m pip install -r requirements.txt
```

如果你使用虚拟环境，确认当前终端已经激活它。

### PowerShell 无法激活虚拟环境

在当前 PowerShell 会话中临时放开执行策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 没有 API Key 能不能跑

可以运行环境检查和单元测试：

```bash
python main.py --check
pytest tests/unit/
```

但真实学习流程（`--demo`、`--file`、交互模式）需要可用的 LLM API Key。

首次运行 `python main.py` 时会自动引导你配置；或手动运行 `python main.py --setup`。

### 为什么 `/direct` 后还要标记待巩固

因为直接看答案绕过了主动回忆。Teacher-skill 的核心判断是：只有用户能自己回答，才算真正掌握。

## 路线图

| 版本 | 目标 | 状态 |
|---|---|---|
| v0.2.0 | GitHub 首发：README、安装文档、Skill 结构、CI | 可发布 |
| v0.3.0 | CLI 可用性：输入体验、控制命令、反馈优化 | 进行中 |
| v0.4.0 | 复习模式：历史归档、自然语言匹配、复习报告 | 基础版完成 |
| v0.5.0 | 教学风格 Persona：严师、良师、苏格拉底、Peer | 待开始 |
| v1.0.0 | 普通用户产品版：Web UI、拖拽上传、可视化进度 | 待开始 |

## 文档入口

| 文档 | 说明 |
|---|---|
| [安装和配置](docs/install/README.md) | 从零运行项目 |
| [项目总览](docs/product/project-overview.md) | 产品定位、机制和模块说明 |
| [PRD](docs/product/PRD.md) | 产品需求文档 |
| [路线图](docs/product/roadmap.md) | 后续开发计划 |
| [当前状态](docs/development/status.md) | 当前可用能力和待办 |
| [发布检查清单](docs/development/release-checklist.md) | 发布前检查项 |
| [变更日志](docs/development/changelog.md) | 重要改动记录 |
| [归档资料](docs/archive/learning-notes/README.md) | 个人学习笔记和历史沉淀 |

## License

MIT
