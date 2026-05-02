# Phase 2 扩展任务 — 复习模式

> **创建日期**：2026-04-23
> **来源**：与用户讨论"回顾之前学习状态"时提出的优化方案
> **阅读建议**：Phase 2 核心任务完成后，开始实现此处列出的扩展任务

---

## 背景问题

当前 Phase 2 设计只支持"继续当前主题"，不支持"复习之前的主题"。

用户复习时需要：
- 能回顾之前学过的内容
- 不需要重新讲解，直接进入提问验证模式
- 基于历史 Q&A 和掌握情况，优先复习薄弱点

---

## 设计方案：自然语言触发复习模式

### 核心思路

跨主题复习模式仍然通过自然语言意图识别触发，例如“复习一下之前学的 transformer”。

注意：v0.3.0 已新增的 `/review` 只是“查看当前 topic 待巩固知识点列表”，不启动跨主题复习流程。

### 流程对比

| 场景 | 正常学习 | 复习模式 |
|------|---------|---------|
| 入口 | 输入新材料 | "我想复习一下..." |
| 讲解 | ✅ 完整讲解 | ❌ 跳过，直接提问 |
| 问题 | ✅ 第一次见 | ✅ 基于历史 Q&A |
| 反馈 | ✅ 正常反馈 | ✅ 正常反馈 |

### 实现层次

```
用户: "复习一下之前学的transformer"

         ↓
┌─────────────────────────────┐
│  意图识别层 (Intent Router)  │  ← 判断是"复习"还是"新学"
└─────────────────────────────┘
         ↓ 复习
┌─────────────────────────────┐
│  主题匹配层 (Topic Matcher) │  ← 从 profile.history_topics 里找最匹配的
└─────────────────────────────┘
         ↓
┌─────────────────────────────┐
│  复习引擎 (Review Engine)   │  ← 加载 history + chunks，跳过讲解
└─────────────────────────────┘
```

---

## 任务清单

### D1. 新建复习 Prompt

**文件**：`prompts/04_review.md`

**内容**：
```
你是复习助手。用户想回顾之前学过的内容。

规则：
- 不再讲解基础概念（用户已经学过）
- 直接抛出验证问题，检验掌握程度
- 如果答错，说明"这个点需要再巩固"，给一个极简提示
- 重点放在"用户之前答错过/标记 needs_review 的 chunk"

输入：
- topic_title: "Transformer 自注意力机制"
- chunks: [ ... ]  # 从 state.json 加载
- history: [ ... ] # 从 history.json 加载，重点关注 fail_count > 0 的 chunk

输出格式同 02_tutor_core.md
```

---

### D2. 意图识别 + 主题匹配

**文件**：`main.py` 或新建 `src/core/router.py`

**实现**：
```python
# 意图关键词
REVIEW_KEYWORDS = ["复习", "回顾", "回忆", "温习", "再看一遍", "再学一遍"]

def _is_review_intent(user_input: str) -> bool:
    """判断用户输入是否具有复习意图"""
    return any(kw in user_input for kw in REVIEW_KEYWORDS)

def _match_topic(user_input: str) -> str | None:
    """从 history_topics 中模糊匹配最接近的主题"""
    # 1. 从 profile.json 加载 history_topics
    # 2. 用用户描述匹配 topic_title 或 familiar_topics
    # 3. 返回最接近的 topic_id
```

---

### D3. profile.json 数据结构扩展

**文件**：`models/user.py`

**更新 `UserProfile` model**：
```python
class LearnedTopic(BaseModel):
    """已学习主题的摘要记录"""
    topic_id: str
    topic_title: str
    learned_at: datetime
    chunk_count: int
    mastered_count: int
    needs_review_count: int

class UserProfile(BaseModel):
    # ... 现有字段 ...

    # 新增字段
    history_topics: List[LearnedTopic] = Field(default_factory=list)
```

---

### D4. 复习引擎核心逻辑

**文件**：`src/core/engine.py` 或新建 `src/core/review_engine.py`

**核心流程**：
```python
def start_review(self, topic_id: str) -> AIMessage:
    """启动复习模式：加载历史，直接进入提问"""
    # 1. 加载 topic state (state.json)
    # 2. 加载 conversation history (history.json)
    # 3. 优先排序：needs_review > 未掌握 > 已掌握
    # 4. 调用 04_review.md 生成复习问题
    # 5. 进入 WAITING_ANSWER 状态

def receive_review_answer(self, answer: str) -> AIMessage:
    """复习模式下的判卷逻辑"""
    # 与正常判卷类似，但反馈措辞更简洁
```

---

### D5. history_topics 写入时机

**位置**：在 `_show_summary()` 或 `_save_progress()` 时更新

**逻辑**：
```python
def _update_history_topics(self, topic_state: TopicState):
    """学完一个主题后，将摘要写入 profile.history_topics"""
    mastered = sum(1 for c in topic_state.chunks if c.status == LearningStatus.MASTERED)
    needs_review = sum(1 for c in topic_state.chunks if c.status == LearningStatus.NEEDS_REVIEW)

    entry = LearnedTopic(
        topic_id=topic_state.topic_id,
        topic_title=topic_state.topic_id,  # 或从 chunks[0] 取 title
        learned_at=datetime.now(),
        chunk_count=topic_state.total_chunks,
        mastered_count=mastered,
        needs_review_count=needs_review,
    )

    # 写入 profile.history_topics（更新或追加）
```

---

## 验收标准

1. 用户输入"复习一下之前学的transformer"能正确识别并加载对应主题
2. 复习模式跳过讲解，直接进入提问
3. 优先提问 `needs_review` 和 `fail_count > 0` 的 chunk
4. 复习完成后更新 `profile.json` 的 `history_topics`

---

## 优先级建议

| 任务 | 优先级 | 理由 |
|------|--------|------|
| D3 | P0 | 数据结构是一切基础 |
| D2 | P0 | 意图识别是入口 |
| D1 | P1 | Prompt 依赖 D2/D3 |
| D4 | P1 | 核心复习逻辑 |
| D5 | P2 | 可以手动维护 history_topics 暂不自动更新 |

---

## 备注

- 复习模式下的判卷反馈措辞应更简洁，不重复讲解
- 考虑增加"连续答对 N 题才算真正掌握"的门槛
- 未来可扩展：基于遗忘曲线自动安排复习时间（SM-2 算法）
