# 变更日志

> **文档规则**：每次完成一个 Phase / Sprint / 重要修复，在此追加记录
> **格式**：按时间倒序，每条记录包含：日期、变更类型、内容、关联文件

---

## 2026-05-07 — 本地网站模式

**体验**
- 新增 `demo_server.py` 轻量录屏服务：`python main.py --web --recording-demo` 会走固定离线网页闭环，不依赖 Pydantic、Rich、API Key 或真实 LLM 响应，便于稳定录制展示视频。
- 新增 `python main.py --web`，启动只监听 `127.0.0.1` 的本地网站，并自动打开浏览器。
- `--web` 启动前会自动复用环境检查；缺少 API Key 或配置时，先进入配置向导，配置成功后继续打开网站。
- `api_server.py` 从单纯 API bridge 扩展为“静态网页 + `/api/analyze`”本地服务器。
- `showcase/` 静态页面接入本地 `/api/analyze`，不需要 Node/Vite 即可作为本地网页入口使用。
- 重构本地网页左侧资料区：支持粘贴资料、分别上传 txt/md/pdf、资料启用/停用、重命名和删除。
- 优化中间对话区：从固定讲解展示改为连续聊天消息流，展示资料接收、分析中、卡片生成、切换知识点、用户回答、判卷反馈和速查反馈。
- 优化右侧学习状态区：新增进度条、当前阶段、当前卡片、资料数量、学习风格选择和下一步提示，减少空白但保持信息分区清晰。
- 调整本地网页学习触发逻辑：上传资料只保存到 Sources，不再自动分析；用户在中间说明学习目标或发送学习请求后，才生成知识卡片并进入问答。
- 优化右侧 Studio 状态流：阶段改为“添加资料 → 说明目标 → 生成卡片 → 问答复习”，并显示当前学习目标，避免用户上传后直接进入验证阶段的错觉。
- 修复右侧 Studio 面板排版压缩问题：取消侧栏 flex 压缩布局，改为稳定滚动流，避免学习风格、知识卡片、学习报告互相重叠。
- 新增网页学习闭环 API：`/api/teach` 负责当前卡片讲解，`/api/judge` 负责用户答案判卷，`/api/hint` 负责渐进提示和速查。
- 前端问答流程接入上述 API：切换知识卡片时请求讲解，提交答案时请求判卷，点击速查时请求提示/直接答案；真实引擎失败时保留本地 fallback。
- 优化网页端意图识别：用户输入“不懂/不会/直接解释/这是什么”等学习请求时，不再误走判卷，而是进入 `/api/teach` 渐进讲解模式；只有正常回答才提交 `/api/judge`。
- 修正首次学习目标分流：如果用户一开始就说“我不懂/直接解释 X 是什么”，生成卡片后会直接进入渐进讲解，而不是先进入标准验证问题。
- `/api/health` 增加 `features` 字段，用于确认当前运行服务是否加载了 `progressive_explain` 等最新能力。
- 新增 `/api/respond` 统一学习响应入口：学习阶段的用户输入先由后端判断为 `answer`、`explain` 或 `direct_answer`，再自动调用 `/api/judge`、`/api/teach` 或 `/api/hint`。
- 前端学习阶段不再依赖关键词正则把输入硬标成“学习请求”；包含“是什么”但实际在作答的句子会进入判卷路径，避免重复触发讲解。
- `/api/health` 的 `supports/features` 增加 `respond`、`backend_intent_routing` 和 `llm_intent_classifier`，用于确认当前运行的是新版服务。
- 拆分讲解请求：普通“不懂/解释一下”进入渐进讲解；“不太能/直接告诉我这个概念”进入 `direct_explain`，只讲清概念，不立即追问验证问题。
- 讲解请求改为用户选择模式：遇到“不懂/不会/直接讲”等输入时，中间对话区先展示“引导我理解”和“直接详细解释”两个入口，由用户选择学习节奏。
- 新增网页录屏演示模式：`python main.py --web --recording-demo` 会打开 `?demo=1`，自动准备固定示例资料、固定 3 张知识卡片和重置演示按钮，便于稳定录制展示视频。

**测试**
- 新增 `tests/unit/test_demo_server.py`，覆盖轻量录屏服务的固定演示数据、直接讲解响应和 `/api/health`。
- 新增 `tests/unit/test_api_server.py`，覆盖本地静态资源解析、防路径穿越，以及不调用真实 LLM 的分析 fallback。
- 扩展 `tests/unit/test_api_server.py`，覆盖 `/api/teach`、`/api/judge`、`/api/hint` 的本地 fallback 路径。
- 补充渐进讲解 fallback 测试，确保“请求解释”不会被当成答错判卷。
- 补充 `/api/respond` 路由测试，覆盖“包含是什么但实际在作答”的判卷分流，以及“明确请求讲解”的渐进讲解分流。
- 补充直接讲解测试，确保用户明确要求“直接告诉我概念”时不会继续追加轻量确认问题。
- 补充 `/api/demo` 固定演示数据测试，确保录屏模式始终有稳定材料和 3 张演示卡片。

**文档**
- README 新增本地网站启动方式，明确该模式不会发布到公网。

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
