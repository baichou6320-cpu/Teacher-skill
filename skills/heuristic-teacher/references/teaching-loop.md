# Teaching Loop Reference

The Teacher-skill loop exists to prevent passive learning.

## Normal Learning Flow

```text
1. Analyze material.
2. Create 3-7 knowledge chunks.
3. Teach the current chunk.
4. Ask one validation question.
5. Receive the user's answer.
6. Judge the answer.
7. If correct, mark mastered and advance.
8. If wrong, provide a progressive hint and retry.
9. If direct answer is requested, mark needs_review and advance.
10. Save progress.
```

## Chunk Requirements

Each chunk should include:

- `chunk_id`
- `title`
- `content`
- `question`
- `correct_answer`
- optional `options`
- optional `analogy`
- `difficulty`

## State Requirements

The runtime should preserve:

- Current chunk index.
- Chunk status: `not_started`, `in_progress`, `mastered`, or `needs_review`.
- Attempt count.
- Failure count.
- Hint level.
- Conversation history.

## Separation of Responsibilities

```text
analyzer: split material into chunks
teach: explain one chunk and ask one question
judge: evaluate the answer and produce feedback
storage: persist state and history
```

Do not collapse these responsibilities into one step.
