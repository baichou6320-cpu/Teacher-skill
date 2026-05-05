# 项目状态总览

> **更新日期**：2026-05-03
> **当前阶段**：v0.3.0 CLI 可用性修复推进中（v0.2.0 已具备 GitHub 首发条件）
> **阅读建议**：每天开工前看一遍，确认今天要修哪个模块

---

## 一、核心能力状态

```
用户输入材料 → LLM 分析切片 → 逐个讲解 → 提问 → 用户回答
    → 判卷 → 正确（标记掌握 + 连击奖励）→ 下一知识点 ✅
    → 判卷 → 错误（渐进提示 hint_level 1-4）→ 重新作答 ✅
    → /direct → 直接给答案（标记 needs_review）→ 下一知识点 ✅
```

**附加能力：**
- `--file` / `/load` 加载本地文件（.md/.txt/.pdf）✅
- Prompt 分层架构（base + persona + system module）✅
- 单元测试无需 API Key 即可运行；本次 CLI 可用性改动新增测试后，需重新跑本地或 CI 确认 ✅
- 标准 Agent Skill 结构已建立：`skills/heuristic-teacher/SKILL.md` ✅
- README 已精简为项目入口，文档已按 product/development/learning-notes/install 分区 ✅
- GitHub Actions 单测工作流已通过 ✅
- `.env.example` 与 `config.yaml` 配置说明已校准：API Key/base_url 在 `.env`，模型参数在 `config.yaml` ✅
- 安装和配置文档已完善：`docs/install/README.md` ✅
- CLI 可用性修复已推进：支持 `--init` 项目初始化、`--check` 启动环境检查（依赖缺失时也能轻量解析配置）、`--demo` 示例体验、推荐 `--file`、支持 `/load` 追加材料、支持 `/skip`/`/back`/`/list`/`/jump`/`/review`、历史 topic 显示可读标题、答案提交确认、温和错误反馈 ✅
- 复习模式已形成可用闭环：完成主题后自动写入 `profile.history_topics`，可用 `/history` 查看历史学习记录，支持“复习一下 xxx”匹配历史主题，按薄弱点优先直接提问，接入复习专用短反馈 Prompt，并在复习结束后输出统计报告、更新 `last_reviewed_at` ✅
- CLI 工程结构已开始模块化：`main.py` 拆出 `src/cli/environment.py`、`src/cli/display.py`、`src/cli/review.py`，入口文件从“所有逻辑集中”转为“入口 + 应用编排 + 兼容包装” ✅

**结论：Phase 2 核心教学闭环 + 工程基建已可用。**

---

## 二、模块状态矩阵

| 模块 | 文件 | 状态 | 备注 |
|------|------|------|------|
| 状态机调度 | `src/core/engine.py` | ✅ 可用 | `TutorState` 管理完整流程，支持 split/merged prompt 模式 |
| 对话记忆 | `src/core/memory.py` | ✅ 已接入 | 上下文注入、历史恢复 |
| 连击激励 | `src/core/rewards.py` | ✅ 已接入 | 答对时追加鼓励语，跨天 streak 计算 |
| LLM 客户端 | `src/llm/client.py` | ✅ 可用 | 重试、thinking 提取、分类异常（timeout/auth/rate-limit） |
| 响应解析 | `src/llm/translator.py` | ✅ 可用 | 4层降级 JSON 提取，边界 case 已补单元测试 |
| 文件加载 | `src/utils/file_loader.py` | ✅ 可用 | .md/.txt（编码回退）/.pdf（pypdf） |
| 文件存储 | `src/utils/storage.py` | ✅ 可用 | 主题隔离 JSON 存储 |
| 集中配置 | `src/utils/config.py` + `config.yaml` | ✅ 已完成 | Pydantic Settings，默认 prompt_mode: split |
| 日志系统 | `src/utils/logger.py` | ✅ 已完成 | 四级日志、按日期轮转落盘 |
| 错误处理 | `src/llm/exceptions.py` + 各处 try-except | ✅ 已完成 | 用户友好提示 + 自动保存进度 |
| Onboarding | `main.py` + `00_onboarding.md` | ✅ 已跑通 | 自动摸底，判定水平 |
| 进度恢复 | `main.py` | ✅ 已可用 | 数字选择恢复 / `new` 创建新主题 |
| 历史持久化 | `main.py` `_save_progress()` | ✅ 已可用 | 保存 `state.json` + `history.json` |
| CLI 辅助模块 | `src/cli/environment.py`、`src/cli/display.py`、`src/cli/review.py` | ✅ 已拆分 | 启动检查、控制台渲染、复习 CLI 从 `main.py` 分离 |
| 单元测试 | `tests/unit/` × 8 文件 | 🚧 部分本地验证通过 | 当前 Codex 环境仍受 Windows 临时目录权限影响，`tmp_path` 类测试无法完整跑；已验证 `test_main_flow.py` 非环境子集、`test_router.py`、`test_engine_navigation.py`、`main.py --check` |
| Agent Skill | `skills/heuristic-teacher/SKILL.md` | ✅ 已建立 | 独立于产品文档，包含工作流与验证标准 |
| CI | `.github/workflows/tests.yml` | ✅ 通过 | GitHub Actions `Tests` workflow 已跑绿 |

---

## 三、发布前待办（P0 — 本周完成即可发 GitHub）

| # | 任务 | 影响 | 预估耗时 |
|---|------|------|---------|
| 1 | **GitHub Actions 跑绿** | 发布前自动验证单测 | ✅ 已通过 |
| 2 | **更新 changelog 发布记录** | 记录结构整理、CI、主流程修复 | ✅ 已完成 |
| 3 | **确认发布包不含本地数据** | 避免提交 `.env`、logs、data、cache | ✅ 已确认 `.gitignore` 保护 |
| 4 | **配置说明校准** | `.env.example` 与 `config.yaml` 的模型配置关系需一致 | ✅ 已完成 |

---

## 四、后续版本路线图

| 版本 | 目标 | 内容 | 状态 |
|------|------|------|------|
| **v0.2.0** | GitHub 首发 | README、安装文档、Skill 结构、CI、发布清单已完成 | ✅ 可发布 |
| **v0.3.0** | CLI 可用性 | 输入体验、学习控制命令、进度感知、答案确认、反馈优化 | 🚧 进行中 |
| **v0.4.0** | 复习模式 | 历史归档、自然语言主题匹配、薄弱点优先直接提问、复习专用 Prompt、复习结束报告已完成 | ✅ 基础版完成 |
| **v0.5.0** | 教学风格 | Persona 体系（严师/良师/苏格拉底/Peer） | ⏳ 待开始 |
| **v1.0.0** | 普通用户产品版 | Web UI、拖拽上传、可视化进度、低门槛配置 | ⏳ 待开始 |

---

## 五、快速验证

```bash
# 单元测试（无需 API Key，CI 可用；本次 CLI 可用性改动后请重新运行）
pytest tests/unit/

# 端到端测试（需要 API Key）
python tests/integration/test_e2e.py

# 直接运行主程序
python main.py
```

---

## 六、Sprint 进度

| Sprint | 内容 | 状态 |
|--------|------|------|
| Sprint 1 | 工程基建（日志、配置、错误处理）| ✅ 已完成 |
| Sprint 2 | 输入扩展（文件读取、PDF）+ 单元测试 | ✅ 已完成 |
| Sprint 3 | Prompt 拆分 + 教学风格 | ✅ Prompt 拆分已完成，Persona 待做 |
