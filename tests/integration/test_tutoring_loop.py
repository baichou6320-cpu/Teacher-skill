"""教学循环测试 — 验证讲解→提问→反馈→推进的完整流程。"""
import os
import sys

# Bootstrap environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests  # noqa: F401

from src.core.engine import TutorEngine
from models.protocol import ResponseType


def test_tutoring_loop() -> None:
    """Test the full tutoring loop: explain → question → answer → feedback → advance."""
    print("=" * 50)
    print("教学循环测试")
    print("=" * 50)

    engine = TutorEngine("test_user", "test_tutoring_topic")

    material = """
    Transformer是一种革命性的深度学习架构，它在2017年的论文《Attention Is All You Need》中被提出。
    核心创新包括自注意力机制、位置编码和多头注意力。
    """

    # Step 1: Analyse material
    print("\n1. 分析材料...")
    topic_state = engine.analyze_material(material)
    assert topic_state.total_chunks >= 2, f"知识点数量不足: {topic_state.total_chunks}"
    print(f"   ✅ 材料分析成功，共 {topic_state.total_chunks} 个知识点")

    # Step 2: Start first chunk
    print("\n2. 开始第一个知识点...")
    response = engine.start_topic(topic_state)
    print(f"   响应类型: {response.response_type}")
    assert response.response_type == ResponseType.QUESTION, f"期望提问，实际: {response.response_type}"
    assert response.chunk_id == topic_state.chunks[0].chunk_id
    print("   ✅ 第一个知识点讲解完成")

    # Step 3: Correct answer
    print("\n3. 模拟用户答对...")
    correct = topic_state.chunks[0].correct_answer
    print(f"   提交正确答案: {correct}")
    response = engine.receive_answer(correct)
    print(f"   响应类型: {response.response_type}")
    assert response.response_type == ResponseType.FEEDBACK_CORRECT, f"期望答对反馈，实际: {response.response_type}"
    print("   ✅ 用户答对")

    # Step 4: Advance to next chunk
    print("\n4. 进入下一个知识点...")
    response = engine.next_chunk()
    print(f"   响应类型: {response.response_type}")
    assert response.response_type == ResponseType.QUESTION, f"期望提问，实际: {response.response_type}"
    assert response.chunk_id == topic_state.chunks[1].chunk_id
    print("   ✅ 进入第二个知识点")

    # Step 5: Wrong answer
    print("\n5. 模拟用户答错...")
    response = engine.receive_answer("这是一个错误的答案")
    print(f"   响应类型: {response.response_type}")
    assert response.response_type in (ResponseType.FEEDBACK_WRONG, ResponseType.FEEDBACK_HINT)
    print(f"   ✅ 收到错误反馈，hint_level: {engine.topic_state.chunks[1].hint_level}")

    # Step 6: /direct (quick mode)
    print("\n6. 测试速查模式 (/direct)...")
    response = engine.receive_answer("", is_direct=True)
    print(f"   响应类型: {response.response_type}")
    assert response.response_type == ResponseType.DIRECT_ANSWER, f"期望直接答案，实际: {response.response_type}"
    assert engine.topic_state.chunks[1].status.value == "needs_review"
    print("   ✅ 速查模式生效，知识点已标记为待巩固")

    # Step 7: Continue
    print("\n7. 继续到下一个知识点...")
    response = engine.next_chunk()
    idx = engine.topic_state.current_chunk_index
    total = engine.topic_state.total_chunks
    print(f"   响应类型: {response.response_type}, 当前索引: {idx}, 总数: {total}")
    if idx < total:
        assert response.response_type == ResponseType.QUESTION
        print("   ✅ 进入下一个知识点")
    else:
        print("   ✅ 已完成所有知识点")

    print("\n" + "=" * 50)
    print("🎉 教学循环测试全部通过！")
    print("=" * 50)


if __name__ == "__main__":
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("⚠️ 跳过测试（需要有效 API Key）")
        sys.exit(0)
    test_tutoring_loop()
