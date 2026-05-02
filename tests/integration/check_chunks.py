"""快速检查材料分析后的切片字段完整性。"""
import os
import sys
from pathlib import Path

# Bootstrap environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests  # noqa: F401

from src.llm.client import LLMClient
from src.llm.translator import ResponseTranslator


client = LLMClient()
translator = ResponseTranslator()

prompt_analyzer = Path("prompts/01_analyzer.md").read_text(encoding="utf-8")
material = (
    "Transformer是一种革命性的深度学习架构，"
    "它在2017年的论文《Attention Is All You Need》中被提出。"
    "核心创新包括自注意力机制、位置编码和多头注意力。"
)
prompt = client.interpolate(prompt_analyzer, {"material": material, "user_level": "beginner"})
response = client.generate(prompt, "请分析以上材料，拆解为知识点", max_tokens=4096)

print("=== 原始响应 ===")
print(response)
print("\n=== 解析结果 ===")
parsed = translator.parse_material_analysis(response)
if parsed:
    for c in parsed.get("chunks", []):
        print(
            f'chunk: {c.get("chunk_id")} | '
            f'title: {c.get("title")} | '
            f'answer: {c.get("answer")} | '
            f'correct_answer: {c.get("correct_answer")}'
        )
else:
    print("解析失败")
