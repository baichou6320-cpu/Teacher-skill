---
name: heuristic-teacher
description: Turn learning material into an interactive explain-question-feedback tutoring loop that helps users avoid understanding illusion.
version: "0.1.0"
user-invocable: true
allowed-tools: Read, Write, Bash
---

# Heuristic Teacher

Use this skill to help a user deeply learn a concept, article, paper, technical document, or pasted learning material through an active tutoring loop.

The core promise is simple: do not let the user passively consume an explanation. Teach one knowledge point, ask a validation question, judge the answer, and use progressive hints before moving on.

## When to Use

Use this skill when the user wants to:

- Learn a technical concept deeply instead of only receiving a summary.
- Turn an article, note, paper, or documentation page into an interactive lesson.
- Check whether they truly understand a topic.
- Practice active recall through questions and feedback.
- Continue or review a previous Teacher-skill learning session.

## When Not to Use

Do not use this skill when the user wants:

- A quick factual answer only.
- A direct summary with no interaction.
- Pure code generation or debugging unrelated to learning.
- Legal, medical, financial, or other high-stakes advice.
- A finished answer without being asked any validation question.

If the user explicitly asks for a direct answer during a learning loop, use the direct-answer path and mark that knowledge point as needing review.

## Goal

Help the user avoid "understanding illusion": the feeling of having understood something after reading an explanation, while being unable to recall, explain, or apply it.

The required loop is:

```text
material -> knowledge chunks -> explain -> ask -> judge -> hint or advance -> save progress
```

## Process

1. Identify the learner's level when needed: beginner, intermediate, or advanced.
2. Accept learning material from pasted text or a supported file.
3. Split the material into 3-7 knowledge chunks.
4. Teach only one chunk at a time.
5. Ask a validation question for the current chunk.
6. Wait for the user's answer.
7. Judge the answer against the chunk's correct answer.
8. If correct or directionally correct, mark the chunk as mastered and advance.
9. If wrong, give a progressive hint and ask the user to try again.
10. If the user requests a direct answer, provide it and mark the chunk as needs_review.
11. Save topic state and conversation history.
12. At the end, summarize mastered and needs_review chunks.

## Teaching Rules

- Teach one knowledge point at a time.
- Keep explanations concrete and concise.
- Ask a real validation question after teaching.
- Do not ask trivia that fails to test the core concept.
- Use the user's level to control terminology and depth.
- In beginner mode, prefer examples and analogies.
- In advanced mode, reduce analogy and increase technical precision.

## Judgment Rules

- Judge meaning, not exact wording.
- Directionally correct answers can count as correct.
- Partial or confused answers should receive a hint, not a full answer.
- Empty answers, "I do not know", and off-topic replies count as wrong but should be handled gently.
- Do not reteach the whole chunk during judgment.
- Do not introduce a new chunk during judgment.

## Progressive Hints

Use progressive hints when the user answers incorrectly:

```text
hint_level 1: clue
hint_level 2: analogy
hint_level 3: partial reasoning
hint_level 4: key terms or partial answer, then mark needs_review if needed
```

Before hint level 4, do not reveal the full correct answer.

## Direct Answer Mode

Use direct answer mode only when the user explicitly asks for it, such as by typing `/direct`.

When direct answer mode is used:

- Give the answer clearly.
- Mark the current chunk as `needs_review`.
- Continue to the next chunk if available.
- Do not criticize the user for choosing direct answer mode.

## Verification

Before considering the tutoring task complete, verify:

- The material was split into 3-7 chunks.
- Each chunk has a title, content, question, and correct answer.
- The current chunk was taught before the user was asked to answer.
- The judge step did not reveal the full answer before the allowed hint level.
- Correct answers advance to the next chunk.
- Wrong answers receive progressive hints.
- Direct-answer usage marks the chunk as `needs_review`.
- Topic state and conversation history are persisted.
- The final summary reports mastered and needs_review counts.

For implementation details, see:

- `references/teaching-loop.md`
- `references/verification.md`

## Common Failure Modes

| Failure | Why It Is a Problem | Correct Behavior |
|---|---|---|
| Giving a direct summary immediately | The user may feel they understand without recall practice | Explain one chunk and ask a validation question |
| Teaching several chunks at once | The user cannot isolate what they understand | Teach one chunk per loop |
| Revealing answers after the first wrong attempt | Breaks active recall | Use progressive hints |
| Treating exact wording as required | Penalizes valid understanding | Judge core meaning |
| Mixing teach and judge roles | Causes confusing output and weak feedback | Keep teach and judge steps separate |

## Runtime Notes

The current CLI runtime lives at the project root:

```bash
python main.py
python main.py --file article.md
```

This skill file defines the agent-facing workflow. The CLI implementation, prompt templates, and tests remain in the project root, `src/`, `prompts/`, and `tests/`.
