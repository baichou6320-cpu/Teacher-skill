# Teacher-skill 项目总览

> **阅读建议**：第一次接触本项目，先读「快速开始」和「命令系统」；想了解架构设计，读「Prompt 架构说明」和「扩展路线图」。

---

# 🎓 Teacher-skill

## 快速开始

```bash
# 1. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动学习
python main.py                    # 交互式启动
python main.py --file article.md  # 从文件加载
```

**核心交互命令**：
- `/learn` — 学习新知识（默认入口）
- `/progress` — 查看当前进度
- `/direct` — 速查模式（直接给答案，标记待巩固）
- `/exit` — 退出并保存进度

---

## 项目定位

### 一句话

**Teacher-skill** 是一个启发式数字助教 CLI 工具，通过「讲解 → 提问 → 反馈」的闭环学习机制，解决"理解幻觉"问题。

### 什么是理解幻觉？

> 看完 AI 的解释后觉得自己懂了，但无法复述核心概念、无法在真实场景中应用、短时间内遗忘。

**解决方案**：把学习过程拆解为知识卡片，逐个讲解 → 提问验证 → 根据对错给予渐进式提示，强迫用户参与思考过程，而非被动接收答案。

### 核心机制

```
用户输入材料 → AI 分析切片 → 逐个讲解 → 提问验证 → 判卷
  ├─ 答对 → 标记掌握 + 连击奖励 → 下一知识点
  ├─ 答错 → 渐进提示(hint 1-4: 线索→类比→半解析→部分答案) → 重新作答
  └─ /direct → 直接给答案（标记 needs_review）→ 下一知识点
```

### 目标用户

- 需要自学 AI/技术文档的初级从业者
- 经常阅读论文或技术资料，但难以理解与应用的读者
- 产品/运营/研发转型人群

---

## 命令系统

所有命令统一以 `/` 开头，在任何状态下都可输入 `/help` 查看帮助。

| 命令 | 功能 | 状态 | 说明 |
|------|------|------|------|
| `/learn` | 学习新知识 | ✅ 可用 | 输入材料，开始新的学习主题 |
| `/review` | 复习旧知识 | 🔨 框架已设计 | 自然语言触发，如"复习一下 transformer" |
| `/create` | 创建自定义老师 | ⏳ 框架已设计 | 选择/调整教学风格，保存为 persona |
| `/progress` | 查看当前进度 | ✅ 可用 | 显示当前知识点 / 总知识点 |
| `/direct` | 速查模式 | ✅ 可用 | 直接给答案，但该知识点标记为待巩固 |
| `/load <path>` | 加载文件 | ✅ 可用 | 加载 `.md` / `.txt` / `.pdf` 作为学习材料 |
| `/help` | 查看帮助 | ✅ 可用 | 显示所有可用命令 |
| `/exit` | 退出并保存 | ✅ 可用 | 保存当前进度，下次可恢复 |

### 命令状态关系

```
[空闲状态]
  ├── /learn ──→ [输入材料] ──→ [教学循环中]
  ├── /review ──→ [主题匹配] ──→ [复习循环中]
  └── /create ──→ [风格配置] ──→ [保存并应用]

[教学循环中]
  ├── /progress ──→ 显示进度
  ├── /direct ──→ 速查（标记待巩固）──→ 下一知识点
  └── /exit ──→ 保存并退出

[复习循环中]
  ├── /progress ──→ 显示复习进度
  └── /exit ──→ 保存并退出
```

---

## 主流程详解

### Learn Flow — 学习新知识

```
用户: /learn

  Step 1: Onboarding（首次使用）
    └── Agent: "在开始学习之前，让我先了解一下你的情况..."
    └── 用户回答背景 → 判定水平: beginner / intermediate / advanced

  Step 2: 输入学习材料
    ├── 方式 A: 直接粘贴文本（输入 /done 结束）
    ├── 方式 B: /load <文件路径>（支持 .md / .txt / .pdf）
    └── 方式 C: python main.py --file <路径>

  Step 3: 材料分析
    └── AI 将材料拆解为 3-7 个知识卡片（chunks）
    └── 每个卡片包含: title / content / question / options / answer / analogy / difficulty

  Step 4: 教学循环（核心）
    └── 对每个 chunk 执行:
        ├── teach: 讲解知识点 → 抛出验证问题
        ├── 用户回答
        └── judge: 判卷 → 正确(下一题) / 错误(hint 1-4 渐进提示)

  Step 5: 完成报告
    └── 掌握: X / 总 Y
    └── 待巩固: Z
    └── 完成率: XX%
    └── 进度自动保存到 data/users/{user_id}/
```

### Review Flow — 复习旧知识（Phase 2 后期实现）

> ⚠️ 框架设计，待实现

```
用户: "复习一下之前学的 transformer"

  Step 1: 意图识别
    └── 检测关键词: "复习" / "回顾" / "再看一遍" / "温习"

  Step 2: 主题匹配
    └── 从 profile.history_topics 中模糊匹配最接近的主题
    └── 返回 topic_id

  Step 3: 加载历史
    └── 加载 state.json（知识点状态）
    └── 加载 history.json（历史 Q&A）
    └── 优先排序: needs_review > fail_count>0 > 已掌握

  Step 4: 复习循环（区别于学习循环）
    └── 跳过讲解，直接提问
    └── 问题基于历史 Q&A 重新生成
    └── 判卷反馈更简洁，不重复讲解基础概念

  Step 5: 更新状态
    └── 更新 profile.history_topics
    └── 更新各 chunk 的掌握状态
```

### Create Flow — 创建自定义老师（Phase 3 实现）

> ⚠️ 框架设计，待实现

```
用户: /create

  Step 1: 选择基础风格
    ├── gentle_mentor — 良师模式（默认）：耐心引导，多鼓励
    ├── strict_teacher — 严师模式：要求高，追问到底
    ├── socratic_guide — 苏格拉底：不直接给答案，只用反问
    └── peer_tutor — Peer 模式：像同学一样平等讨论

  Step 2: 调整参数
    ├── 耐心度（1-5）: 答错后提示的详细程度
    ├── 鼓励频率（1-5）: 正向反馈的密度
    ├── 追问深度（1-5）: 答对后是否追问延伸问题
    └── 术语密度（1-5）: 讲解中专业术语的占比

  Step 3: 预览效果
    └── 用同一知识点测试不同参数的效果
    └── 用户确认或继续调整

  Step 4: 保存并应用
    └── 保存为 prompts/personas/{custom_name}.md
    └── 替换 _persona.md 或动态加载
    └── 写入 user.profile.preferred_persona
```

---

## Prompt 架构说明

### 为什么分层？

之前的 `02_tutor_core.md` 把讲解+判卷+反馈揉在一个文件里，导致：
1. LLM 角色混淆（讲解时突然判卷）
2. 内容单薄（96 行无法覆盖所有场景）
3. 无法扩展（新增功能只能继续平铺）

**分层架构 = 关注点分离**：把"不变的部分"和"随场景变化的部分"拆开。

### 目录结构

```
prompts/
├── _base.md              # 通用协议层（所有 Prompt 共享）
│   └── 身份定义 + 能力清单 + JSON 输出协议 + 质量标准 + 禁止事项
├── _persona.md           # 人设层（可替换的教学风格）
│   └── 性格特质 + 交互原则 + 语气规范
├── system/               # 系统功能层（各模块专用指令）
│   ├── 00_onboarding.md  # 用户水平摸底
│   ├── 01_analyzer.md    # 材料分析 + 知识切片
│   ├── 02_teach.md       # 讲解 + 提问
│   ├── 03_judge.md       # 判卷 + 渐进提示
│   └── 04_review.md      # 复习模式（未来）
└── personas/             # 风格扩展层（Phase 3）
    ├── gentle_mentor.md  # 默认风格
    ├── strict_teacher.md # 严师模式
    ├── socratic_guide.md # 苏格拉底
    └── peer_tutor.md     # Peer 模式
```

### 拼接逻辑

engine.py 根据当前场景，自动拼接对应的 Prompt 层：

| 场景 | 拼接组合 |
|------|---------|
| 水平摸底 | `_base + _persona + 00_onboarding` |
| 材料分析 | `_base + 01_analyzer` |
| 讲解提问 | `_base + _persona + 02_teach` |
| 判卷反馈 | `_base + _persona + 03_judge` |
| 复习模式 | `_base + _persona + 04_review`（未来）|

### 修改指南

| 你想改什么 | 改哪个文件 | 影响范围 |
|-----------|-----------|---------|
| 教学风格（语气、性格） | `_persona.md` 或 `personas/*.md` | 所有教学交互 |
| 输出格式规范 | `_base.md` | 所有模块 |
| 讲解策略 | `system/02_teach.md` | 仅讲解阶段 |
| 判卷标准 | `system/03_judge.md` | 仅判卷阶段 |
| 新增功能模块 | `system/` 下新建文件 | 新功能 |

### 向后兼容

`config.yaml` 中 `prompt_mode: "split"`（默认）使用分层架构。
设置为 `"merged"` 可切回旧的 `02_tutor_core.md`。

---

## 代码集成

### 当前调用方式

**CLI 入口**：
```bash
python main.py              # 交互式启动
python main.py --file path  # 从文件加载
```

**核心模块**：
| 模块 | 文件 | 职责 |
|------|------|------|
| 状态机 | `src/core/engine.py` | 教学循环调度、Prompt 拼接 |
| LLM 客户端 | `src/llm/client.py` | API 调用、重试、thinking 提取 |
| 响应解析 | `src/llm/translator.py` | 4层降级 JSON 提取 |
| 文件加载 | `src/utils/file_loader.py` | .md/.txt/.pdf 读取 |
| 配置 | `src/utils/config.py` | 集中配置管理 |
| 存储 | `src/utils/storage.py` | JSON 文件读写 |

### 未来 API 化（Phase 4）

```python
from src.core.engine import TutorEngine

engine = TutorEngine(user_id="user_001", topic_id="topic_001")

# 分析材料
topic_state = engine.analyze_material(material, user_level="beginner")

# 开始教学
response = engine.start_topic(topic_state)

# 接收回答
response = engine.receive_answer("用户的回答")

# 获取进度
progress = engine.get_progress()  # "2/5"
```

---

## 扩展路线图

### Phase 2 工程化（当前）

| 任务 | 状态 | 说明 |
|------|------|------|
| 日志系统 | ✅ 完成 | 四级日志、按日期轮转 |
| 集中配置 | ✅ 完成 | config.yaml + config.py |
| 文件输入 | ✅ 完成 | .md/.txt/.pdf 支持 |
| Prompt 拆分 | ✅ 完成 | 分层架构 |
| 错误处理 | ✅ 完成 | LLM 超时/断网友好提示 |
| 单元测试 | ⏳ 待做 | pytest，不依赖真实 LLM |
| 复习模式 | 🔨 框架已设计 | /review 命令 |

### Phase 3 Skill 体系

| 任务 | 状态 | 说明 |
|------|------|------|
| 自定义老师 | ⏳ 框架已设计 | /create 命令，4种基础风格 |
| 风格参数化 | ⏳ 待做 | 耐心度、鼓励频率等可调参数 |
| Skill 保存/分享 | ⏳ 待做 | 导出/导入 persona 文件 |
| 多用户支持 | ⏳ 待做 | 脱离 default_user hardcode |

### Phase 4 多宿主

| 任务 | 状态 | 说明 |
|------|------|------|
| Claude Code Skill 化 | ⏳ 待做 | 通过 `skills/heuristic-teacher/SKILL.md` 被宿主加载 |
| API 服务化 | ⏳ 待做 | 提供 HTTP API 接口 |
| Web UI | ⏳ 待做 | 浏览器端交互界面 |

---

## 文档地图

| 文档 | 内容 | 什么时候读 |
|------|------|-----------|
| **docs/product/project-overview.md（本文件）** | 全景图：定位、命令、流程、架构、路线图 | **第一次接触时读** |
| skills/heuristic-teacher/SKILL.md | Agent Skill 核心工作流 | 给 Agent 安装/执行时读 |
| RULES.md | 开发规则：代码规范、模块边界、开工 checklist | 新 Agent 会话时读 |
| README.md | 快速启动：安装、运行、验证 | 想快速上手时读 |
| docs/development/status.md | 实时状态：当前进度、阻塞问题 | 每天开工前读 |
| docs/product/roadmap.md | 开发计划与路线图 | 决定"今天做什么"时读 |
| docs/product/PRD.md | 产品需求：为什么做 | 想了解背景时读 |
| docs/development/changelog.md | 变更日志 | 查某功能什么时候加的 |
| docs/product/review-mode.md | 复习模式扩展设计 | Phase 2 后期实现时读 |
