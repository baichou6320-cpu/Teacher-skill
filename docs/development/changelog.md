# 变更日志

> **文档规则**：每次完成一个 Phase / Sprint / 重要修复，在此追加记录
> **格式**：按时间倒序，每条记录包含：日期、变更类型、内容、关联文件

---

## [未发布] — v0.2.0 发布准备

> 详见 [docs/product/roadmap.md](../product/roadmap.md)

**测试**
- 新增 `tests/unit/test_main_flow.py`，覆盖 `main.py` 主流程：
  - 恢复主题不会重复启动教学
  - 最后一题答对后正常退出学习循环
  - 最后一题使用 `/direct` 后正常退出学习循环
- 本地单元测试已通过：`pytest tests/unit/`，102/102 ✅

**修复**
- 修复 `main.py` Windows 输出编码处理：改用 `sys.stdout.reconfigure()` / `sys.stderr.reconfigure()`，避免 pytest 捕获流被替换后出现 `lost sys.stderr`。
- 修复 `main.py` 恢复主题重复讲解问题。
- 修复 `main.py` 最后一题完成后不退出学习循环的问题。

**工程**
- 补充 `PyYAML>=6.0.0` 到 `requirements.txt`，确保 `src/utils/config.py` 的 `yaml` 依赖在 CI 和新环境中可用。
- 新增 GitHub Actions 单测工作流：`.github/workflows/tests.yml`。
- GitHub Actions `Tests` workflow 已通过 ✅。
- 校准 `.env.example` 与 `config.yaml`：`.env` 只保留 API Key 和可选 base_url，模型与生成参数统一由 `config.yaml` 管理。

**文档**
- README 精简为项目入口页。
- 新增完整安装和配置说明：`docs/install/README.md`。
- 新建标准 Agent Skill 结构：`skills/heuristic-teacher/SKILL.md`。
- 重整文档目录为 `docs/product/`、`docs/development/`、`docs/learning-notes/`、`docs/install/`。
- 新增发布检查清单：`docs/development/release-checklist.md`。

**体验**
- 推荐 `python main.py --file <路径>` 作为主要学习入口。
- 新主题输入阶段支持 `/load <路径>` 加载文件，不再默认要求粘贴文本后输入 `/done`。
- 多行粘贴改为显式 `/paste` 模式，降低普通输入时的困惑。
- 学习过程中支持 `/load <路径>` 追加材料，新材料会分析成新的知识点并追加到当前 topic。
- 新增学习控制命令：`/skip`、`/back`、`/list`、`/jump N`、`/review`。
- 强化 `/progress`，显示已掌握、待巩固、未开始、作答次数和答错次数。

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
- 新增 `tests/test_tutoring_loop.py` — 教学循环全流程测试
- `test_debug.py`、`test_e2e.py`、`test_tutoring_loop.py` 全部验证通过 ✅

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
