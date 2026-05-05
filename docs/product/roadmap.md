# 版本路线图

> **当前版本**：v0.2.0-ready（Phase 2 核心已完成，GitHub 首发准备完成）
> **更新日期**：2026-05-02

---

## v0.2.0 — GitHub 首发

**目标**：功能已完备，完成发布前清理、文档同步和 CI 验证。

### 发布 Checklist

- [x] 核心教学闭环（讲解→提问→判卷→反馈）
- [x] 工程基建（日志、配置、错误处理）
- [x] 文件输入（.md/.txt/.pdf）
- [x] Prompt 分层架构（split/merged 双模式）
- [x] 单元测试 102 个全部通过
- [x] LICENSE（MIT）
- [x] tests/ 目录整理（unit / integration 分离）
- [x] README 精简为项目入口
- [x] 状态文档同步
- [x] 标准 Agent Skill 结构：`skills/heuristic-teacher/SKILL.md`
- [x] 安装文档：`docs/install/README.md`
- [x] GitHub Actions 单测工作流通过

**验收**：clone → `pip install -r requirements.txt` → `pytest tests/unit/` 全绿 → `python main.py` 能跑。

---

## v0.3.0 — CLI 可用性修复（预计 1 周）

**目标**：让用户在 CLI 中也有控制感，减少输入和学习过程中的挫败感。

### 任务

| # | 任务 | 文件 | 备注 |
|---|------|------|------|
| C1 | 推荐 `--file` 作为主要入口 | `README.md` / `main.py` | ✅ 已完成 |
| C2 | 新主题阶段支持 `/load <路径>` | `main.py` | ✅ 已完成 |
| C3 | 多行粘贴改为显式 `/paste` | `main.py` | ✅ 已完成 |
| C4 | 学习中支持 `/load <路径>` 追加材料 | `main.py` / `engine.py` | ✅ 已完成 |
| C5 | 增加学习控制命令 | `main.py` / `engine.py` | `/skip`、`/back`、`/list`、`/jump N`、`/review`，✅ 已完成 |
| C6 | 强化 `/progress` | `main.py` | 显示掌握、待巩固、未开始、作答统计，✅ 已完成 |
| C7 | topic 可读标题 | `models/state.py` / `storage.py` / `main.py` | ✅ 已完成 |
| C8 | 答案提交确认 | `main.py` | ✅ 已完成：Enter 提交，`/edit` 修改，`/cancel` 取消 |
| C9 | 错误反馈情绪优化 | `main.py` / prompt | ✅ 已完成：温和反馈面板 + hint_level 可见说明 |
| C10 | Demo 示例模式 | `main.py` / `samples/demo_article.md` | ✅ 已完成：`python main.py --demo` 使用内置材料体验 |
| C11 | 启动环境检查 | `main.py` / `README.md` / `docs/install/README.md` | ✅ 已完成：`python main.py --check` 检查 API Key、配置、依赖和 demo 材料 |
| C12 | 项目初始化 | `main.py` / `README.md` / `docs/install/README.md` | ✅ 已完成：`python main.py --init` 创建 `.env`、数据目录和日志目录 |

**验收**：
1. 用户可以用 `python main.py --demo` 不准备材料直接体验
2. 用户可以用 `python main.py --file article.md` 直接开始学习
3. 用户可以用 `python main.py --check` 在正式启动前检查配置是否完整
4. 用户可以用 `python main.py --init` 自动准备本地配置，不需要手动复制 `.env.example`
5. 用户可以在新主题和学习过程中使用 `/load <路径>`
6. 用户可以使用 `/skip`、`/back`、`/list`、`/jump N`、`/review` 控制学习流程
7. `/progress` 不只是显示 `3/7`，还显示掌握、待巩固和答题统计
8. 用户提交答案前可以确认、修改或取消
9. 答错反馈不再只显示红色错误，而是展示温和提示和当前提示层级

---

## v0.4.0 — 复习模式（预计 1 周）

**目标**：支持"回顾之前学过的内容"，跳过讲解直接提问验证。

### 任务

| # | 任务 | 文件 | 备注 |
|---|------|------|------|
| D1 | 创建 `prompts/system/04_review.md` | 复习专用 Prompt | ✅ 已完成：短反馈、快推进、薄弱点保留待巩固 |
| D2 | 意图识别 + 主题匹配 | `src/core/router.py` / `main.py` | ✅ 已完成：识别“复习一下 xxx”并匹配 `history_topics` |
| D3 | profile 数据结构扩展 | `models/user.py` | ✅ 已完成：`history_topics: List[LearnedTopic]` |
| D4 | 复习引擎核心逻辑 | `src/core/engine.py` / `main.py` | ✅ 基础版完成：跳过讲解，按薄弱点优先直接提问 |
| D5 | history_topics 自动写入 | `main.py` `_show_summary()` 时更新 | ✅ 已完成：学完主题后自动归档，`/history` 可查看 |
| D6 | 复习结束报告 | `main.py` | ✅ 已完成：输出本轮统计、仍待巩固列表，并更新 `last_reviewed_at` |

**验收**：
1. 输入"复习一下之前学的 transformer"能正确识别并加载对应主题
2. 复习模式跳过讲解，直接进入提问
3. 优先提问 `needs_review` 和 `fail_count > 0` 的 chunk
4. 复习完成后更新 `profile.json` 的 `history_topics`
5. 复习结束后能看到本轮作答、答对、速查、跳过、仍待巩固知识点

---

## v0.5.0 — 教学风格 Persona（预计 1 周）

**目标**：让教学从"千篇一律"变成"因人而异"。

### 任务

| # | 任务 | 文件 | 备注 |
|---|------|------|------|
| E1 | 创建 `models/persona.py` | `TeachingPersona` Pydantic 模型 | 定义风格字段 |
| E2 | 创建 `prompts/personas/` 目录 | 4 个风格文件 | strict / gentle / socratic / peer |
| E3 | onboarding 增加风格选择 | `main.py` + `00_onboarding.md` | 用户首次使用时选择 |
| E4 | 保存 preferred_persona 到 profile | `models/user.py` + `storage.py` | 持久化 |
| E5 | Engine 动态拼接 persona prompt | `engine.py` `_get_system_prompt()` | 根据用户选择加载对应 persona |

**风格预览**：

| ID | 名称 | 特点 |
|----|------|------|
| `strict_teacher` | 严师模式 | 要求高，追问到底，鼓励少 |
| `gentle_mentor` | 良师模式 | 耐心引导，多鼓励，默认 |
| `socratic_guide` | 苏格拉底 | 不直接给答案，只用反问 |
| `peer_tutor` | Peer 模式 | 像同学一样平等讨论 |

**验收**：选择"严师"后，AI 语气明显更严厉；选择"苏格拉底"后，从不直接给答案。

---

## v1.0.0 — Skill 体系（Phase 3）

**目标**：把项目变成可分享、可复用的 Skill。

### 方向（待细化）

- Skill 保存/分享格式（JSON/YAML）
- Claude Code Skill 化（`.claude/skills/` 兼容）
- 社区 Prompt 模板市场（基础框架）

---

## 风险与应对

| 风险 | 概率 | 应对 |
|------|------|------|
| Persona 风格差异不明显 | 中 | 先做 2 个风格验证，再扩展 |
| 复习模式意图识别不准 | 中 | 先用关键词匹配，后期可升级 LLM 意图识别 |
| API 费用（Prompt 拆分后）| 高 | 已保留 merged 模式开关，用户可自由切换 |

---

## 历史 Sprint（已归档）

| Sprint | 内容 | 状态 | 完成日期 |
|--------|------|------|---------|
| Sprint 1 | 工程基建（日志 A1、配置 A2、错误处理 A3）| ✅ | 2026-04-20 |
| Sprint 2 | 输入扩展 + 测试（文件读取 B1/B2、单元测试 A4）| ✅ | 2026-04-29 |
| Sprint 3 | Prompt 拆分（C4）| ✅ | 2026-04-29 |
