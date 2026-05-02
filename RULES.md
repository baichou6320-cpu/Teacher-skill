# RULES.md — 新会话必读

> **作用**：每次开新会话时，让 Agent 先读此文件，快速理解项目上下文、当前状态和协作规则。
> **阅读时间**：2 分钟

---

## 1. 项目定位（一句话）

**Teacher-skill** 是一个启发式数字助教 CLI 工具，通过「讲解 → 提问 → 反馈」闭环解决"理解幻觉"问题。

---

## 2. 当前阶段与目标

| 阶段 | 状态 | 目标 |
|------|------|------|
| Phase 1：核心教学闭环 | ✅ 已完成 | 讲解→提问→判卷→反馈，全流程已跑通 |
| Phase 2：工程化 + 输入扩展 | 🔨 **进行中** | 日志✅、配置✅、**文件输入✅**、错误处理、Prompt拆分、单元测试 |
| Phase 3：Skill 体系 | ⏳ 待开始 | 教学风格配置、Skill 保存/分享 |
| Phase 4：多宿主 | ⏳ 待开始 | Claude Code Skill 化 |

**当前剩余 P0 阻塞问题**：
1. ~~无文件输入~~ → ✅ **已完成**
2. ~~判卷与教学混用~~ → ✅ **已完成**（分层 Prompt 架构：_base + _persona + teach/judge）
3. **错误处理不完善** → LLM 超时/断网直接抛异常崩溃

---

## 3. 文档地图（新会话必读顺序）

**按此顺序阅读，不要跳过：**

```
1. docs/product/project-overview.md ← 全景图：定位、命令、流程、架构、路线图
2. RULES.md（本文件）           ← 开发规则与协作规范
3. docs/development/status.md   ← 项目实时状态，确认今天修哪个模块
4. docs/product/roadmap.md      ← 任务清单，决定"今天做什么"
5. README.md                    ← 快速启动、安装运行
6. skills/heuristic-teacher/SKILL.md ← Agent Skill 核心工作流
```

**按需阅读：**
- `docs/product/PRD.md` — 了解"为什么做"（产品需求）
- `docs/development/changelog.md` — 查某功能什么时候加的
- `docs/product/review-mode.md` — 复习模式扩展设计
- `CLAUDE.md` — 开发规范、代码风格、模块边界
- `docs/product/decisions.md` — 技术决策日志（重要决策记录处）

---

## 4. 开发原则（必须遵守）

### 4.1 先读代码，再动手
- 修改任何模块前，必须先读该模块的源码
- 要求 Agent 用以下格式解释代码后再修改：
  ```
  做什么：
  不做什么：
  职责边界：
    Input:
    Output:
  ```

### 4.2 最小侵入
- 不改现有核心循环（`engine.py` 状态机不动），只在外围增强
- 新增功能默认关闭或可配置，不破坏现有 CLI 流程

### 4.3 文档同步
- 每完成一个任务，同步更新 `docs/development/status.md`
- 重要技术决策记录到 `docs/product/decisions.md`

### 4.4 代码风格
- Python：Google docstring + type hints 必须
- 错误处理：不允许裸 `try-except`，必须指定异常类型
- Prompt 文件：Markdown 格式，包含 ` ```json ` 包裹的 JSON 输出示例

---

## 5. 项目结构速查

```
Teacher-skill/
├── main.py                 # CLI 唯一入口
├── src/
│   ├── core/
│   │   ├── engine.py       # 状态机调度（教学循环控制）
│   │   ├── memory.py       # 短期对话记忆
│   │   └── rewards.py      # 连击激励
│   ├── llm/
│   │   ├── client.py       # LLM 客户端（重试、多服务商兼容）
│   │   └── translator.py   # 结构化解析器（4层降级 JSON 提取）
│   └── utils/
│       ├── storage.py      # 主题隔离 JSON 存储
│       ├── config.py       # 集中配置（config.yaml）
│       └── logger.py       # 日志系统（按日期轮转）
│       └── file_loader.py  # 文件加载器（md/txt/pdf）← Phase 2 新增
├── models/                 # Pydantic 数据模型
├── prompts/                # Prompt 模板（给 LLM 看的）
├── tests/                  # 测试脚本
├── docs/                   # 📄 项目文档（按编号顺序阅读）
└── data/                   # 用户数据（JSON 存储，不入 git）
```

**模块边界（禁止越界）：**
| 模块 | 职责 | 不做什么 |
|------|------|---------|
| `engine.py` | 状态机调度、教学循环控制 | 不直接调用 LLM |
| `client.py` | LLM API 调用、重试、thinking 提取 | 不解析响应 |
| `translator.py` | 解析 LLM JSON 响应 | 不调用 LLM |
| `storage.py` | JSON 文件读写 | 不处理业务逻辑 |
| `file_loader.py` | 文件内容读取 | 不处理业务逻辑 |

---

## 6. 开工检查清单

每次新会话开始时，Agent 必须完成：

```
1. [ ] 已读 docs/development/status.md，确认当前状态
2. [ ] 已读 docs/product/roadmap.md，确认任务归属 Sprint
3. [ ] 如果要编码，确认任务属于 Phase 2 任务看板中的某一项
4. [ ] 如果要新增任务，先记录到对应文档，不直接开始写代码
5. [ ] 代码改动后，用"代码讲解仪式"确认理解
6. [ ] 重要决策记录到 docs/product/decisions.md
```

---

## 7. 快速验证

```bash
# 端到端测试
python tests/test_e2e.py

# 教学循环全流程测试
python tests/test_tutoring_loop.py

# 直接运行主程序
python main.py

# 从文件加载（Phase 2 新增）
python main.py --file ./your_material.md
```

---

## 8. 最近一次修改

- **2026-04-29**：完成文件输入功能（`.md` / `.txt` / `.pdf` 支持）
  - 新增 `src/utils/file_loader.py`
  - `main.py` 支持 `--file` 命令行参数 + `/load` 交互命令
  - 整理文档，删除过时 archive，同步状态到代码实际
