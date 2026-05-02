"""端到端测试 — 验证 LLM 连接、变量替换和材料分析。"""
import os

# Bootstrap environment (adds project root to sys.path, fixes UTF-8, loads .env)
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests  # noqa: F401

from src.core.engine import TutorEngine
from src.llm.client import LLMClient


# ─── Tests ───


def test_llm_connection() -> bool:
    """Verify basic LLM connectivity."""
    print("=" * 50)
    print("测试 1: LLM 连接")
    print("=" * 50)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    model_id = os.getenv("MODEL_ID")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    print(f"API Key: {api_key[:20]}...")
    print(f"Model ID: {model_id}")
    print(f"Base URL: {base_url}\n")

    try:
        client = LLMClient(api_key=api_key, model_id=model_id, base_url=base_url)
        response = client.generate(
            system_prompt="你是一个简单的助手，只说'你好'。",
            user_message="说你好",
            max_tokens=100,
        )
        print(f"✅ LLM 连接成功！")
        print(f"响应: {response}")
        return True
    except Exception as exc:
        print(f"❌ LLM 连接失败: {exc}")
        return False


def test_variable_interpolation() -> bool:
    """Verify prompt variable interpolation."""
    print("\n" + "=" * 50)
    print("测试 2: 变量替换")
    print("=" * 50)

    template = "用户水平：{{user_level}}，学习主题：{{topic}}"
    variables = {"user_level": "beginner", "topic": "机器学习"}

    result = LLMClient.interpolate(template, variables)
    print(f"模板: {template}")
    print(f"变量: {variables}")
    print(f"结果: {result}")

    if result == "用户水平：beginner，学习主题：机器学习":
        print("✅ 变量替换正常")
        return True
    print("❌ 变量替换异常")
    return False


def test_material_analysis() -> bool:
    """Verify material analysis via the analyzer prompt."""
    print("\n" + "=" * 50)
    print("测试 3: 材料分析")
    print("=" * 50)

    try:
        engine = TutorEngine("test_user", "test_topic")

        material = """
        Transformer是一种革命性的深度学习架构，它在2017年的论文《Attention Is All You Need》中被提出。

        核心创新：
        1. 自注意力机制（Self-Attention）：让模型能够同时关注输入序列的不同位置
        2. 位置编码（Positional Encoding）：因为没有循环结构，需要手动添加位置信息
        3. 多头注意力（Multi-Head Attention）：多组注意力机制并行学习不同特征

        Transformer的优势：
        - 可以并行计算，训练速度快
        - 能够捕捉长距离依赖关系
        - 容易扩展到更大的模型
        """

        print("正在分析材料...")
        topic_state = engine.analyze_material(material)

        print(f"\n✅ 材料分析成功！")
        print(f"主题: {topic_state.topic_id}")
        print(f"知识点数量: {topic_state.total_chunks}\n")

        for i, chunk in enumerate(topic_state.chunks):
            print(f"  [{i+1}] {chunk.title}")
            print(f"      问题: {chunk.question}\n")

        return True
    except Exception as exc:
        print(f"❌ 材料分析失败: {exc}")
        import traceback

        traceback.print_exc()
        return False


# ─── Main ───


def main() -> None:
    print("🎓 Teacher-skill 端到端测试\n")

    results: list[tuple[str, bool]] = []
    results.append(("LLM 连接", test_llm_connection()))
    results.append(("变量替换", test_variable_interpolation()))

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and api_key != "your_api_key_here":
        results.append(("材料分析", test_material_analysis()))
    else:
        print("\n⚠️ 跳过材料分析测试（需要有效 API Key）")

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    for name, passed in results:
        print(f"  {name}: {'✅ 通过' if passed else '❌ 失败'}")

    if all(passed for _, passed in results):
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️ 部分测试失败，请检查配置")


if __name__ == "__main__":
    main()
