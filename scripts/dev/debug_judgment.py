"""调试脚本 — 手动调用判卷逻辑，打印原始响应和解析结果。"""
import os
import sys
from pathlib import Path

# Bootstrap environment
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
import tests  # noqa: F401

from src.core.engine import TutorEngine
from src.llm.translator import ResponseTranslator


engine = TutorEngine("test", "test3")
material = (
    "Transformer是一种革命性的深度学习架构，"
    "它在2017年的论文《Attention Is All You Need》中被提出。"
    "核心创新包括自注意力机制、位置编码和多头注意力。"
)
ts = engine.analyze_material(material)
engine.start_topic(ts)

# Simulate a correct answer
chunk = ts.chunks[0]
answer = chunk.correct_answer
print(f"正确答案: {answer}")

# Build judgment context (mirrors engine.receive_answer internal logic)
parts = [
    f"当前知识点 (1/{ts.total_chunks}):",
    f"=== 知识点 ===\n{chunk.title}\n{chunk.content}",
    f"=== 问题 ===\n{chunk.question}",
]
if chunk.options:
    parts.append("=== 选项 ===\n" + "\n".join(chunk.options))
parts.extend([
    f"=== 用户回答 ===\n{answer}",
    f"=== 正确答案 ===\n{chunk.correct_answer}",
    f"=== 错误次数 ===\n{chunk.fail_count}",
    f"=== 当前提示层级 ===\n{chunk.hint_level}",
])
if chunk.analogy:
    parts.append(f"=== 生活类比 ===\n{chunk.analogy}")

context = "\n\n".join(parts)
user_msg = (
    f"请判断用户回答是否正确，并给出反馈。\n\n{context}\n\n"
    "判断规则：\n"
    "- 如果正确（答对或方向正确），标记 is_correct: true\n"
    "- 如果错误，给出渐进式提示（hint_level 1-4）\n"
    "- hint_level=1: 提供线索提示\n"
    "- hint_level=2: 提供生活类比\n"
    "- hint_level=3: 提供半解析\n"
    "- hint_level=4+: 给出部分答案\n\n"
    '请以 JSON 格式输出：\n'
    '{\n  "is_correct": true/false,\n  "feedback": "反馈内容",\n  "hint_level": 1-4,\n  "action": "continue/next_chunk/complete"\n}'
)

response = engine._call_llm(engine._get_system_prompt("judge"), user_msg, max_tokens=1024)
print("\n=== LLM 原始响应 ===")
print(response)

parsed = ResponseTranslator().parse_judgment(response)
print("\n=== 解析结果 ===")
print(parsed)
