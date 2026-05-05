# Teaching Loop Reference

This reference is for agents that need to implement, debug, or improve the Teacher-skill teaching workflow.

Use it when touching:

- `src/core/engine.py`
- `main.py`
- `src/cli/review.py`
- `src/cli/display.py`
- prompt files under `prompts/system/`
- tests that verify learning, review, navigation, or judgment behavior

The purpose of the loop is to prevent passive learning. A user should not merely receive a summary. The system should repeatedly require active recall, judge the answer, and decide whether to advance, hint, or mark a knowledge point for review.

---

## Table of Contents

- [Core Promise](#core-promise)
- [Mental Model](#mental-model)
- [Data Contracts](#data-contracts)
- [Topic and Chunk Invariants](#topic-and-chunk-invariants)
- [Normal Learning Flow](#normal-learning-flow)
- [Review Flow](#review-flow)
- [Command Handling](#command-handling)
- [Judgment Rules](#judgment-rules)
- [Progressive Hint Rules](#progressive-hint-rules)
- [State Transitions](#state-transitions)
- [Persistence Rules](#persistence-rules)
- [Prompt Responsibilities](#prompt-responsibilities)
- [Implementation Map](#implementation-map)
- [Testing Map](#testing-map)
- [Common Bugs and Correct Fixes](#common-bugs-and-correct-fixes)
- [Minimum Acceptance Checklist](#minimum-acceptance-checklist)

---

## Core Promise

The product promise is:

```text
Material -> chunks -> teach one chunk -> ask one question -> judge answer -> hint or advance -> save progress
```

The loop is successful only when the user proves understanding through an answer.

Do not treat these as proof of understanding:

- The user says “懂了” without answering.
- The user reads a long explanation.
- The user asks for `/direct`.
- The user repeats isolated keywords without explaining the relationship.

Only count a chunk as mastered when the user gives a meaningfully correct answer.

---

## Mental Model

Think of Teacher-skill as four separate workers:

```text
Analyzer -> Teacher -> Judge -> Storage
```

Each worker has a narrow job.

| Worker | Input | Output | Must Not Do |
|---|---|---|---|
| Analyzer | raw material + user level | 3-7 structured chunks | teach, judge, or summarize the whole topic |
| Teacher | one current chunk | explanation + one validation question | judge the user or reveal the answer |
| Judge | current chunk + user answer | correctness, feedback, hint level, next action | introduce a new chunk |
| Storage | topic state + memory | saved JSON files | change learning decisions |

If a change mixes these responsibilities, the teaching loop usually becomes harder to test.

---

## Data Contracts

### `TopicState`

Each topic is a persistent learning session.

Required fields:

```text
topic_id
user_id
title
summary
source_type
source_path
material_chars
created_at
updated_at
current_chunk_index
total_chunks
chunks
is_completed
```

Rules:

- `current_chunk_index` is zero-based.
- `total_chunks` must equal `len(chunks)` after analysis or append.
- `is_completed` should only become true after the final chunk is advanced or the review queue is complete.
- `title`, `summary`, and source metadata should be human-readable because they appear in history and resume lists.

### `ChunkState`

Each chunk is one learnable knowledge point.

Required fields:

```text
chunk_id
title
content
question
correct_answer
difficulty
status
fail_count
hint_level
attempts
mastered_at
```

Optional fields:

```text
options
analogy
```

Rules:

- `content` explains the concept.
- `question` checks whether the user understood the concept.
- `correct_answer` defines what a correct answer must contain.
- `analogy` can support hints, especially for beginners.
- `status` must be one of `not_started`, `in_progress`, `mastered`, `needs_review`.

### `AIMessage`

Runtime responses should use a structured message shape:

```text
response_type
content
chunk_id
question
options
correct_answer
hint_level
is_final
```

Expected response types:

| Type | Meaning | Typical Use |
|---|---|---|
| `explanation` | explanatory message | completion, navigation messages, non-question notices |
| `question` | asks the user to answer | teaching and review prompts |
| `feedback_correct` | user answered correctly | mark mastered, then advance |
| `feedback_wrong` | user answer is wrong | hint and retry |
| `feedback_hint` | user needs more support | hint and retry or mark review |
| `direct_answer` | user asked to see answer | mark needs_review, then advance |

---

## Topic and Chunk Invariants

These conditions should remain true after every user action:

- There is at most one current chunk.
- The current chunk index is within bounds unless the topic is complete.
- A chunk cannot be both `mastered` and `needs_review`.
- `/direct` never marks a chunk as mastered.
- `/skip` never marks a chunk as mastered.
- Correct answer on the final chunk completes the topic.
- Resume should not call `start_topic()` again before restoring memory.
- Appending material must not interrupt the current question.
- Review mode should not reteach before asking.

When debugging, check these invariants before changing prompts.

---

## Normal Learning Flow

Normal learning starts from new material or a resumed topic.

### 1. Analyze Material

Input:

```text
raw material
user_level: beginner | intermediate | advanced
```

Output:

```text
TopicState with 3-7 ChunkState items
```

Analyzer requirements:

- Produce 3-7 chunks for ordinary material.
- Prefer fewer chunks for short material.
- Prefer more chunks only when the material contains clearly separate concepts.
- Use readable chunk titles.
- Generate questions that test understanding, not trivia.
- Generate `correct_answer` as a semantic target, not a single exact phrase.

Bad chunking:

```text
Chunk 1: paragraph 1
Chunk 2: paragraph 2
Chunk 3: paragraph 3
```

Better chunking:

```text
Chunk 1: What the concept means
Chunk 2: Why it works
Chunk 3: How to distinguish it from a similar concept
Chunk 4: How to apply it in a real scenario
```

### 2. Start Topic

`start_topic(topic_state)` should:

1. Store the topic state in the engine.
2. Set the current chunk to `in_progress`.
3. Teach only the current chunk.
4. Return an `AIMessage` with `response_type="question"`.

It should not:

- Advance to the next chunk.
- Mark anything mastered.
- Save directly if the caller owns persistence.
- Teach multiple chunks at once.

### 3. Teach Current Chunk

A teaching response should contain:

```text
short explanation
one validation question
optional options
progress indicator
```

The explanation should be sized to the user level.

| Level | Teaching Style |
|---|---|
| beginner | plain language, concrete example, optional analogy |
| intermediate | concept + mechanism + small example |
| advanced | precise definition, boundary, tradeoff, edge case |

Do not over-explain so much that the validation question becomes meaningless.

### 4. Receive Answer

`receive_answer(answer, is_direct=False)` should first decide whether this is direct-answer mode.

If `is_direct=True`:

1. Return a `direct_answer` message.
2. Mark current chunk as `needs_review`.
3. Do not increment mastery.
4. Allow the caller to advance to the next chunk.

If `is_direct=False`:

1. Increment `attempts`.
2. Send current chunk and user answer to judge.
3. Parse judgment.
4. Update chunk state.
5. Return feedback.

### 5. Correct Answer

When the judge says the answer is correct or directionally correct:

1. Set chunk status to `mastered`.
2. Set `mastered_at`.
3. Return `feedback_correct`.
4. Let the caller call `next_chunk()`.

The caller should then:

- Advance if another chunk exists.
- Complete and summarize if this was the final chunk.

### 6. Wrong Answer

When the answer is wrong:

1. Increment `fail_count`.
2. Increase or preserve `hint_level` according to prompt result.
3. Return `feedback_wrong` or `feedback_hint`.
4. Keep the same current chunk unless hint level requires moving on.

If the user has reached the maximum useful hint level and still cannot answer:

- Mark the chunk as `needs_review`.
- Return final feedback for this item.
- Advance to the next chunk.

### 7. Advance

`next_chunk()` should:

1. Move from current chunk to the next chunk.
2. If the next chunk exists, mark it `in_progress`.
3. Return a new `question` response.
4. If no next chunk exists, set topic `is_completed=True` and return final `explanation`.

Never skip final completion just because the last answer was correct. The final chunk must still trigger summary behavior.

---

## Review Flow

Review mode is for previously learned topics. It checks memory; it is not a full reteaching session.

### Review Queue

Build review priority from weakest to strongest:

1. `status == needs_review`
2. `fail_count > 0`
3. `hint_level > 0`
4. remaining mastered or untouched chunks, if the session reviews everything

The current implementation should prioritize weak chunks first.

### Start Review

`start_review(topic_state)` should:

1. Build the review queue.
2. Set review mode active.
3. Move `current_chunk_index` to the first review item.
4. Return a `question` response.

It should not:

- Call the normal teaching prompt.
- Explain the whole chunk again.
- Reset historical fail counts.

### Review Answer

Review judgment should be shorter than learning judgment.

Correct answer:

- Mark current chunk `mastered`.
- Advance to next review item.

Wrong answer:

- Give short feedback.
- Keep or mark `needs_review`.
- Advance only when the response is final for that item.

`/direct` in review:

- Show direct answer.
- Keep the chunk in `needs_review`.
- Advance to next review item.

`/skip` in review:

- Mark or keep `needs_review`.
- Advance to next review item.

### Review Completion

At the end of review:

1. Show answered/correct/direct/skipped stats.
2. Show remaining review item count.
3. Update topic metadata in `profile.history_topics`.
4. Set or refresh `last_reviewed_at`.
5. Save progress.

---

## Command Handling

Commands should be handled before ordinary answer judgment.

| Command | Learning Mode | Review Mode | State Effect |
|---|---|---|---|
| `/help` | show help | show help | none |
| `/progress` | show progress | show progress | none |
| `/list` | show all chunks | show all chunks | none |
| `/review` | show weak chunks | show weak chunks | none |
| `/history` | show archived topics | show archived topics | none |
| `/direct` | show answer, mark review, advance | show answer, keep review, advance | `needs_review` |
| `/skip` | skip chunk, mark review, advance | skip review item, keep review | `needs_review` |
| `/back` | go to previous chunk | usually not used | changes current index |
| `/jump N` | go to selected chunk | usually not used | changes current index |
| `/load path` | append material to current topic | reject or defer | may add chunks |
| `/exit` | save and exit | save and exit | persists state |

Important:

- Do not send commands to the judge prompt.
- Do not count commands as answer attempts, except when the command explicitly chooses `/direct` or `/skip`.
- Invalid command arguments should show usage and keep the current question active.

---

## Judgment Rules

Judge the meaning of the answer, not exact wording.

### Correct

Count as correct when:

- The core relationship is right.
- The user can explain the idea in their own words.
- Minor terminology is wrong but the concept is clear.
- The answer is incomplete but sufficient for the current question.

Feedback style:

```text
对，这个意思成立。
更精炼地说：...
```

### Partial

Treat as partial when:

- One part is correct, but a key condition is missing.
- The user confuses cause and effect.
- The user gives an example but cannot explain the rule.
- The user names a concept but cannot describe what it does.

Feedback style:

```text
你抓到了 {correct_part}，但还缺 {missing_part}。
提示 1/4：...
你再试一次。
```

### Wrong

Treat as wrong when:

- The answer contradicts the chunk.
- The answer is off-topic.
- The user says they do not know.
- The answer only repeats the question.

Feedback should stay encouraging and specific.

Do not say only:

```text
错了。
```

Instead:

```text
还差一点。先抓住这个方向：...
```

---

## Progressive Hint Rules

Hints should preserve active recall.

| Level | Name | What to Provide | What to Avoid |
|---|---|---|---|
| 1 | clue | direction, key distinction, where to look | answer terms |
| 2 | analogy | familiar comparison | overlong story |
| 3 | partial reasoning | first half of reasoning chain | complete conclusion |
| 4 | key terms / partial answer | important terms or missing relation | pretending user mastered it |

After hint level 4:

- If the user still cannot answer, mark `needs_review`.
- Move forward to protect learning rhythm.
- Make it clear the topic can be reviewed later.

Do not reveal the full `correct_answer` at levels 1-3.

---

## State Transitions

Normal learning states:

```text
IDLE
  -> ANALYZING
  -> TEACHING
  -> WAITING_ANSWER
  -> PROVIDING_HINT
  -> WAITING_ANSWER
  -> COMPLETED
```

Chunk status transitions:

```text
not_started -> in_progress
in_progress -> mastered
in_progress -> needs_review
needs_review -> mastered      # possible during review
mastered -> needs_review      # only if later direct/skip/failure proves instability
```

Avoid transitions:

```text
not_started -> mastered       # user never answered
needs_review -> mastered      # without a correct review answer
direct_answer -> mastered     # direct answer is not recall
skip -> mastered              # skip is not recall
```

---

## Persistence Rules

Save progress after meaningful state changes:

- topic created
- material analyzed
- answer judged
- chunk advanced
- `/direct`
- `/skip`
- `/back`
- `/jump`
- `/load` append succeeds
- review session completes
- user exits

Persist:

```text
state.json
history.json
profile.json
```

Do not commit user runtime data:

```text
.env
logs/
data/users/
__pycache__/
.pytest_cache/
```

---

## Prompt Responsibilities

Keep prompt modules separated.

| Prompt | Role | Required Output |
|---|---|---|
| `00_onboarding.md` | infer learner level | level + explanation |
| `01_analyzer.md` | split material into chunks | topic metadata + chunks |
| `02_teach.md` | teach one chunk and ask | `AIMessage` question |
| `03_judge.md` | judge normal learning answer | correctness + feedback + action |
| `04_review.md` | judge review answer | shorter feedback + review action |

Do not make the analyzer produce final teaching prose.

Do not make the teach prompt judge the user's answer.

Do not make the judge prompt introduce a new chunk.

---

## Implementation Map

Use this map before editing code.

| Need | File |
|---|---|
| Analyze material and create chunks | `src/core/engine.py::analyze_material` |
| Start teaching a topic | `src/core/engine.py::start_topic` |
| Judge answers | `src/core/engine.py::receive_answer` |
| Advance chunks | `src/core/engine.py::next_chunk` |
| Skip/back/jump | `src/core/engine.py::skip_current_chunk`, `previous_chunk`, `jump_to_chunk` |
| Start review | `src/core/engine.py::start_review` |
| Advance review | `src/core/engine.py::next_review_chunk`, `skip_review_chunk` |
| CLI learning loop | `main.py::_learning_loop` |
| CLI review loop | `src/cli/review.py` |
| CLI display | `src/cli/display.py` |
| Topic and chunk models | `models/state.py` |
| User profile and history | `models/user.py` |
| Storage | `src/utils/storage.py` |

When changing a behavior, update the test closest to that behavior.

---

## Testing Map

Recommended tests:

```bash
pytest tests/unit/test_engine_navigation.py
pytest tests/unit/test_main_flow.py
pytest tests/unit/test_router.py
pytest tests/unit/test_translator.py
pytest tests/unit/
```

What each test area should protect:

| Test File | Protects |
|---|---|
| `test_engine_navigation.py` | skip/back/jump/review queue/engine transitions |
| `test_main_flow.py` | CLI loop, answer confirmation, demo, history, review summary |
| `test_router.py` | natural-language review intent and topic matching |
| `test_translator.py` | model output parsing and judgment parsing |
| `test_storage.py` | persisted state and history |
| `test_file_loader.py` | `.md`, `.txt`, `.pdf` material loading |
| `test_config.py` | config and environment assumptions |

If full pytest is blocked by local Windows temp directory permissions, run focused tests and state the blocker clearly. Do not claim the full suite passed.

---

## Common Bugs and Correct Fixes

| Bug | Likely Cause | Correct Fix |
|---|---|---|
| Resume repeats opening question | `start_topic()` called before restored state is used | Restore memory and enter loop without reinitializing teaching |
| Final chunk never completes | Correct feedback returned but `next_chunk()` not called | Ensure correct final answer advances to final response |
| `/direct` marks mastered | Direct answer path shares correct-answer state update | Separate direct path and set `needs_review` |
| Commands are judged as answers | CLI loop checks commands too late | Handle commands before answer confirmation and judgment |
| Wrong answer reveals answer immediately | Judge prompt too permissive or hint logic skipped | Enforce progressive hint levels |
| Review mode reteaches | Review path calls normal teach function | Use review-specific question flow |
| Appended material interrupts current question | Append resets current index or restarts topic | Add chunks to end and keep current index |
| History shows unreadable IDs only | Missing title/source metadata | Fill topic title, summary, source_type, source_path |
| Tests fail only on `tmp_path` | Windows temp permission issue | Run in normal PowerShell or CI; do not rewrite logic blindly |

---

## Minimum Acceptance Checklist

Before considering teaching-loop work complete, verify:

- Material becomes 3-7 meaningful chunks.
- Each chunk has title, content, question, correct answer, and difficulty.
- The user sees only one chunk at a time.
- Every taught chunk ends with one validation question.
- Correct answers mark `mastered` and advance.
- Wrong answers produce progressive hints without revealing full answer too early.
- `/direct` marks `needs_review`.
- `/skip` marks `needs_review`.
- `/back` and `/jump` do not corrupt progress.
- `/load` appends material without interrupting the current question.
- Resume does not duplicate the first teaching message.
- Final chunk produces a summary.
- Review mode asks first and teaches only when needed.
- Review completion updates history metadata.
- State and history are saved after meaningful changes.
- Relevant unit tests pass, or any environment blocker is clearly reported.

If these are true, the loop is behaving like an active tutor instead of a passive summarizer.
