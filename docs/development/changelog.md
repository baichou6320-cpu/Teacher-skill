# 变更日志

> **文档规则**：每次完成一个 Phase / Sprint / 重要修复，在此追加记录
> **格式**：按时间倒序，每条记录包含：日期、变更类型、内容、关联文件

---

## 2026-05-06 — 公开仓库结构整理

**整理**
- 将个人学习笔记从 `docs/learning-notes/` 归档到 `docs/archive/learning-notes/`。
- 将手动 LLM 烟测脚本移动到 `scripts/smoke/`，将开发调试脚本移动到 `scripts/dev/`。
- 将旧版 merged prompt 移动到 `prompts/legacy/`，默认 split prompt 结构保持在 `prompts/system/`。
- 将示例学习材料移动到 `samples/sample_article.md`，方便下载后直接试用。

**文档**
- 新增 `docs/README.md`、`scripts/README.md`、`prompts/README.md`，补齐目录导航。
- 更新 README、安装文档、发布清单和项目规则中的旧路径。

---

## [未发布] — v0.2.0 发布准备

> 详见 [docs/product/roadmap.md](../product/roadmap.md)

**测试**
- 新增 `tests/unit/test_main_flow.py`，覆盖 `main.py` 主流程：
  - 恢复主题不会重复启动教学
  - 最后一题答对后正常退出学习循环
  - 最后一题使用 `/direct` 后正常退出学习循环
- 扩展 `tests/unit/test_main_flow.py`，覆盖复习报告统计、复习完成后 profile 元数据更新、已重新掌握的旧错题不再计入薄弱点。
- 扩展 `tests/unit/test_main_flow.py`，覆盖 `--check` 启动环境检查的缺 API Key 与配置正常两类情况。
- 扩展 `tests/unit/test_main_flow.py`，覆盖 `--init` 初始化 `.env`、运行目录，以及不覆盖已有 `.env` 的行为。
- 此前本地单元测试已通过：`pytest tests/unit/`，102/102 ✅；本次复习报告改动需在补齐 pytest 环境后重新验证。

**修复**
- 修复 `main.py` Windows 输出编码处理：改用 `sys.stdout.reconfigure()` / `sys.stderr.reconfigure()`，避免 pytest 捕获流被替换后出现 `lost sys.stderr`。
- 修复 `main.py` 恢复主题重复讲解问题。
- 修复 `main.py` 最后一题完成后不退出学习循环的问题。

**工程**
- 补充 `PyYAML>=6.0.0` 到 `requirements.txt`，确保 `src/utils/config.py` 的 `yaml` 依赖在 CI 和新环境中可用。
- 新增 GitHub Actions 单测工作流：`.github/workflows/tests.yml`。
- GitHub Actions `Tests` workflow 已通过 ✅。
- 校准 `.env.example` 与 `config.yaml`：`.env` 只保留 API Key 和可选 base_url，模型与生成参数统一由 `config.yaml` 管理。
- 拆分 `main.py`：将启动初始化/环境检查迁移到 `src/cli/environment.py`，将 Rich 控制台渲染迁移到 `src/cli/display.py`，将复习模式 CLI 流程与统计迁移到 `src/cli/review.py`；`main.py` 保留入口、应用编排和兼容包装。

**文档**
- README 精简为项目入口页。
- 新增完整安装和配置说明：`docs/install/README.md`。
- 新建标准 Agent Skill 结构：`skills/heuristic-teacher/SKILL.md`。
- 重整文档目录为 `docs/product/`、`docs/development/`、`docs/install/`；学习笔记后续归档到 `docs/archive/learning-notes/`。
- 新增发布检查清单：`docs/development/release-checklist.md`。

**体验**
- 新增 `python main.py --demo` 示例模式，使用内置短文体验完整学习闭环，降低第一次试用门槛。
- 新增 `python main.py --init` 项目初始化入口：自动创建 `.env`、数据目录和日志目录，且不会覆盖已有 `.env`。
- 新增 `python main.py --check` 启动环境检查，集中检查 API Key、`config.yaml`、运行依赖、测试依赖和 demo 示例材料，并给出修复建议。
- 优化 `--check`：当 `PyYAML` / `pydantic` 尚未安装时，改用标准库轻量解析 `config.yaml`，避免把“依赖未安装”误报成“配置文件读取失败”。
- 推荐 `python main.py --file <路径>` 作为主要学习入口。
- 新增自然语言复习入口：识别“复习一下 xxx”，从 `history_topics` 匹配历史主题。
- 新增复习模式基础版：匹配主题后跳过重新讲解，优先提问待巩固、答错过或用过提示的知识点。
- 新增复习专用 Prompt：`prompts/system/04_review.md`，复习判卷采用短反馈和快推进策略。
- 新增复习结束报告：显示本轮作答、答对、速查、跳过、仍待巩固数量，并列出复习后仍需要巩固的知识点。
- 复习完成后更新 `profile.history_topics.last_reviewed_at`、掌握数和待巩固数，`/history` 增加“上次复习”列。
- 新主题输入阶段支持 `/load <路径>` 加载文件，不再默认要求粘贴文本后输入 `/done`。
- 多行粘贴改为显式 `/paste` 模式，降低普通输入时的困惑。
- 学习过程中支持 `/load <路径>` 追加材料，新材料会分析成新的知识点并追加到当前 topic。
- 新增学习控制命令：`/skip`、`/back`、`/list`、`/jump N`、`/review`。
- 强化 `/progress`，显示已掌握、待巩固、未开始、作答次数和答错次数。
- 为 topic 增加可读标题、摘要、来源和材料长度元数据，历史主题列表不再只显示机器 ID。
- 新增答案提交确认：普通回答会先确认，支持 Enter 提交、`/edit` 修改、`/cancel` 取消。
- 优化错误反馈体验：答错时展示温和提示面板，并明确当前 hint_level 层级和可选动作。
- 扩展用户档案：新增 `LearnedTopic` 和 `history_topics`，主题完成后自动归档，并支持 `/history` 查看历史学习记录。

---

## 2026-04-20 — 文档体系重建

**文档**
- 重建项目文档体系，建立命名规范：
  - `README.md` — 项目入口（1页纸）
  - `docs/product/PRD.md` — 产品需求
  - `docs/development/status.md` — 项目实时状态
  - `docs/product/roadmap.md` — 当前阶段开发计划
  - `docs/development/changelog.md` — 变更日志
- 重写 `PROJECT_STATUS.md`，同步代码真实状态
- 创建 `PLAN_v1.md`（Phase 2 完整计划）
- 创建 `ISSUES_v1.md`（Phase 2 任务清单）
- 归档旧文档：`DEVELOPMENT_PLAN.md` → `docs/archive/old_development_plan.md`
- 归档旧文档：`Week1_Task_Checklist.md` → `docs/archive/week1_dev_log.md`

---

## 2026-04-16 — 核心闭环修复

**修复**
- LLM 返回 thinking 内容导致 JSON 解析失败 → `client.py` 增加 thinking 提取逻辑
- Prompt 约束力弱 → `01_analyzer.md`、`02_tutor_core.md` 强制 ` ```json ` 包裹
- Translator 无法解析混合响应 → `translator.py` 增加 thinking+JSON 混合提取、AIMessage 判卷格式兼容
- Windows 控制台中文乱码 → `main.py`、测试脚本增加 UTF-8 输出修复
- Engine 中 `correct_answer` 字段为空 → 字段映射修复 `answer` → `correct_answer`
- 多次答错后流程卡死 → 自动标记 `NEEDS_REVIEW` 并推进到下一知识点

**测试**
- 新增教学循环全流程测试脚本（当前归档为 `scripts/smoke/tutoring_loop_check.py`）。
- 调试和端到端脚本已归档到 `scripts/dev/` 与 `scripts/smoke/`。

---

## 2026-04-15 — Phase 1 完成

**架构**
- 搭建完整目录结构：`src/core/`、`src/llm/`、`src/utils/`、`models/`、`prompts/`、`tests/`
- 定义 Pydantic 数据模型：`protocol.py`、`state.py`、`user.py`
- 实现 `LLMClient`（Anthropic SDK，支持 base_url 切换服务商）
- 实现 `ResponseTranslator`（4层降级 JSON 解析）
- 实现 `TopicStorage`（主题隔离 JSON 存储）

**核心闭环**
- 实现 `TutorEngine` 状态机：`IDLE → ONBOARDING → ANALYZING → TEACHING → WAITING_ANSWER → PROVIDING_HINT → COMPLETED`
- 实现材料分析 → 知识切片（3-7 个 chunk）
- 实现讲解 → 提问 → 判卷 → 反馈循环
- 实现渐进式提示：`hint_level` 1-4
- 实现速查模式：`/direct` 指令
- 实现进度持久化：`state.json` + `history.json`

**文档**
- 创建 `PRD.md` — 产品需求文档
- 创建 `DEVELOPMENT_PLAN.md` — 五阶段开发计划
- 创建 `PROJECT_STATUS.md` — 项目状态记录
- 创建 `Week1_Task_Checklist.md` — Week1 详细任务日志

---

## 变更类型说明

| 类型 | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 |
| `docs` | 文档 |
| `refactor` | 重构 |
| `test` | 测试 |
| `chore` | 工程/构建 |
