"""Review-mode CLI helpers.

The functions operate on the application object to keep the public behavior in
``main.py`` stable while moving review-specific flow out of the entry module.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return "" if raw is None else str(raw)


def review_topic(
    app: Any,
    topic_id: str,
    *,
    engine_factory,
    topic_state_model,
    output_console,
    panel_cls,
    escape_func,
) -> None:
    """Start review mode for a previously learned topic."""
    app.logger.info(f"Reviewing topic {topic_id}")
    output_console.print(f"\n[cyan]正在进入复习模式：{topic_id}...[/cyan]")
    state_data = app.storage.load_topic_state(topic_id)
    history_data = app.storage.load_conversation_history(topic_id)

    if not state_data:
        app.logger.error(f"Failed to load topic state for review: {topic_id}")
        output_console.print("[red]无法加载该主题的学习进度[/red]")
        return

    topic_state = topic_state_model.model_validate(state_data)
    app.current_engine = engine_factory(app.user_id, topic_id)
    if history_data and history_data.get("messages"):
        app.current_engine.restore_memory(history_data["messages"])

    output_console.print(
        panel_cls.fit(
            f"[bold cyan]复习模式：{escape_func(topic_state.title or topic_id)}[/bold cyan]\n\n"
            "本轮会优先提问待巩固、答错过或用过提示的知识点。\n"
            "[dim]复习模式会直接提问，不重新讲解；可用 /direct 查看答案，/skip 跳过。[/dim]",
            border_style="cyan",
        )
    )
    response = app.current_engine.start_review(topic_state)
    app._display_response(response)
    if response.is_final:
        app._finish_review_session(topic_state, app._new_review_stats())
        return

    app._review_loop(topic_state)
    app._save_progress()


def run_review_loop(app: Any, topic_state: Any, *, output_console, sys_module) -> None:
    """Run review mode without re-teaching each chunk."""
    app.logger.info(f"Review loop started: {topic_state.total_chunks} chunks")
    review_stats = app._new_review_stats()

    while True:
        user_input = output_console.input("\n[bold blue复习>[/bold blue] ").strip()
        if not user_input:
            continue

        lowered = user_input.lower()
        if lowered in ("/help", "help"):
            app._show_help()
            continue

        if lowered in ("/exit", "/quit", "exit", "quit"):
            app.logger.info("User requested exit from review, saving progress")
            app._save_progress()
            output_console.print("[cyan]已保存复习进度，下次再见！[/cyan]")
            sys_module.exit(0)

        if lowered == "/direct":
            response = app.current_engine.receive_answer("", is_direct=True)
            app._record_review_result(review_stats, response, is_direct=True)
            app._display_response(response)
            if app._advance_review_or_finish():
                app._finish_review_session(topic_state, review_stats)
                break
            continue

        if lowered == "/progress":
            app._show_progress()
            continue

        if lowered == "/list":
            app._show_chunk_list()
            continue

        if lowered == "/review":
            app._show_review_items()
            continue

        if lowered == "/history":
            app._show_history_topics()
            continue

        if lowered == "/skip":
            response = app.current_engine.skip_review_chunk()
            app._record_review_result(review_stats, response, is_skipped=True)
            app._display_response(response)
            app._save_progress()
            if response.is_final:
                app._finish_review_session(topic_state, review_stats)
                break
            continue

        if app._parse_load_command(user_input) is not None:
            output_console.print("[yellow]复习模式暂不追加材料；请退出后用 /load 或 --file 学习新材料。[/yellow]")
            continue

        confirmed_answer = app._confirm_answer_submission(user_input)
        if confirmed_answer is None:
            continue

        app.logger.debug(f"Review answer: {confirmed_answer[:50]}...")
        response = app.current_engine.receive_answer(confirmed_answer, is_direct=False)
        app._record_review_result(review_stats, response)
        app._display_response(response)

        if app._review_response_finishes_item(response):
            if app._advance_review_or_finish():
                app._finish_review_session(topic_state, review_stats)
                break


def new_review_stats() -> dict[str, int]:
    """Create counters for one review session."""
    return {
        "answered": 0,
        "correct": 0,
        "direct": 0,
        "skipped": 0,
        "kept_review": 0,
    }


def record_review_result(
    stats: dict[str, int],
    response: Any,
    *,
    is_direct: bool = False,
    is_skipped: bool = False,
) -> None:
    """Update review-session counters from one user action."""
    if is_skipped:
        stats["skipped"] += 1
        stats["kept_review"] += 1
        return

    if is_direct:
        stats["direct"] += 1
        stats["kept_review"] += 1
        return

    stats["answered"] += 1
    response_type = _enum_value(response.response_type)
    if response_type == "feedback_correct":
        stats["correct"] += 1
        return

    if response.is_final and response_type in ("feedback_wrong", "feedback_hint"):
        stats["kept_review"] += 1


def review_response_finishes_item(response: Any) -> bool:
    """Return whether a review response should move to the next review item."""
    response_type = _enum_value(response.response_type)
    return response_type in ("feedback_correct", "direct_answer") or (
        response.is_final
        and response_type in ("feedback_wrong", "feedback_hint")
    )


def advance_review_or_finish(app: Any) -> bool:
    """Move to the next review item and return whether the queue is complete."""
    response = app.current_engine.next_review_chunk()
    app._display_response(response)
    return response.is_final


def finish_review_session(app: Any, topic_state: Any, review_stats: dict[str, int]) -> None:
    """Show review summary and persist review metadata."""
    app._show_review_summary(topic_state, review_stats)
    app._record_review_completion(topic_state)
    app._save_progress()


def remaining_review_items(app: Any, topic_state: Any) -> list[tuple[int, Any]]:
    """Return chunks that still need attention after a review session."""
    return [
        (i, chunk)
        for i, chunk in enumerate(topic_state.chunks, 1)
        if app._chunk_still_needs_review(chunk)
    ]


def chunk_still_needs_review(chunk: Any) -> bool:
    """Decide whether a chunk remains weak after the current review."""
    status = _enum_value(chunk.status)
    if status == "needs_review":
        return True
    return status != "mastered" and (
        int(chunk.fail_count or 0) > 0 or int(chunk.hint_level or 0) > 0
    )


def record_review_completion(app: Any, topic_state: Any, *, learned_topic_cls) -> None:
    """Update history metadata after a review session finishes."""
    profile = app._load_or_create_profile()
    now = datetime.now()
    total = len(topic_state.chunks)
    mastered = sum(1 for c in topic_state.chunks if _enum_value(c.status) == "mastered")
    needs_review = len(app._remaining_review_items(topic_state))

    for topic in profile.history_topics:
        if topic.topic_id == topic_state.topic_id:
            topic.title = topic_state.title or topic.title or topic.topic_id
            topic.summary = topic_state.summary or topic.summary
            topic.total_chunks = total
            topic.mastered_chunks = mastered
            topic.review_chunks = needs_review
            topic.source_type = topic_state.source_type
            topic.source_path = topic_state.source_path
            topic.last_reviewed_at = now
            break
    else:
        profile.history_topics.insert(
            0,
            learned_topic_cls(
                topic_id=topic_state.topic_id,
                title=topic_state.title or topic_state.topic_id,
                summary=topic_state.summary,
                completed_at=topic_state.created_at,
                total_chunks=total,
                mastered_chunks=mastered,
                review_chunks=needs_review,
                source_type=topic_state.source_type,
                source_path=topic_state.source_path,
                last_reviewed_at=now,
            ),
        )

    profile.total_topics = len(profile.history_topics)
    profile.completed_topics = len(profile.history_topics)
    profile.updated_at = now
    app.storage.save_user_profile(profile.model_dump(mode="json"))

