# 版本路线图

> **当前版本**：v0.2.0-dev（Phase 2 核心已完成，准备 GitHub 首发）
> **更新日期**：2026-04-29

---

## v0.2.0 — GitHub 首发（本周）

**目标**：功能已完备，做发布前的清理与文档同步。

### 发布 Checklist

- [x] 核心教学闭环（讲解→提问→判卷→反馈）
- [x] 工程基建（日志、配置、错误处理）
- [x] 文件输入（.md/.txt/.pdf）
- [x] Prompt 分层架构（split/merged 双模式）
- [x] 单元测试 99 个全部通过
- [x] LICENSE（MIT）
- [x] tests/ 目录整理（unit / integration 分离）
- [x] README 结构图同步
- [x] 状态文档同步

**验收**：clone → `pip install -r requirements.txt` → `pytest tests/unit/` 全绿 → `python main.py` 能跑。

---

## v0.3.0 — 教学风格 Persona（预计 1 周）

**目标**：让教学从"千篇一律"变成"因人而异"。

### 任务

| # | 任务 | 文件 | 备注 |
|---|------|------|------|
| C1 | 创建 `models/persona.py` | `TeachingPersona` Pydantic 模型 | 定义风格字段 |
| C2 | 创建 `prompts/personas/` 目录 | 4 个风格文件 | strict / gentle / socratic / peer |
| C3 | onboarding 增加风格选择 | `main.py` + `00_onboarding.md` | 用户首次使用时选择 |
| C4 | 保存 preferred_persona 到 profile | `models/user.py` + `storage.py` | 持久化 |
| C5 | Engine 动态拼接 persona prompt | `engine.py` `_get_system_prompt()` | 根据用户选择加载对应 persona |

**风格预览**：

| ID | 名称 | 特点 |
|----|------|------|
| `strict_teacher` | 严师模式 | 要求高，追问到底，鼓励少 |
| `gentle_mentor` | 良师模式 | 耐心引导，多鼓励，默认 |
| `socratic_guide` | 苏格拉底 | 不直接给答案，只用反问 |
| `peer_tutor` | Peer 模式 | 像同学一样平等讨论 |

**验收**：选择"严师"后，AI 语气明显更严厉；选择"苏格拉底"后，从不直接给答案。

---

## v0.4.0 — 复习模式（预计 1 周）

**目标**：支持"回顾之前学过的内容"，跳过讲解直接提问验证。

### 任务

| # | 任务 | 文件 | 备注 |
|---|------|------|------|
| D1 | 创建 `prompts/04_review.md` | 复习专用 Prompt | 跳过讲解，直接提问 |
| D2 | 意图识别 + 主题匹配 | `src/core/router.py` 或 `main.py` | 关键词触发复习模式 |
| D3 | profile 数据结构扩展 | `models/user.py` | `history_topics: List[LearnedTopic]` |
| D4 | 复习引擎核心逻辑 | `src/core/review_engine.py` | 加载历史，薄弱点优先 |
| D5 | history_topics 自动写入 | `engine.py` `_show_summary()` 时更新 | 学完主题后自动归档 |

**验收**：
1. 输入"复习一下之前学的 transformer"能正确识别并加载对应主题
2. 复习模式跳过讲解，直接进入提问
3. 优先提问 `needs_review` 和 `fail_count > 0` 的 chunk
4. 复习完成后更新 `profile.json` 的 `history_topics`

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
