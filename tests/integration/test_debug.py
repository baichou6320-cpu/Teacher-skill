"""调试脚本 — 查看 LLM 原始响应和解析结果。"""
import json
import os
import sys
from pathlib import Path

# Bootstrap environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tests  # noqa: F401

from src.llm.client import LLMClient
from src.llm.translator import ResponseTranslator


# ─── Run ───

client = LLMClient()
translator = ResponseTranslator()

prompt_analyzer = (Path(__file__).parent.parent / "prompts" / "01_analyzer.md").read_text(
    encoding="utf-8"
)

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

prompt = client.interpolate(prompt_analyzer, {"material": material, "user_level": "beginner"})

print("调用 LLM...")
response = client.generate(prompt, "", max_tokens=4096)

# Save to file
with open("debug_output.txt", "w", encoding="utf-8") as f:
    f.write("=== LLM 原始响应 ===\n")
    f.write(response)
    f.write(f"\n\n=== 响应长度 ===\n{len(response)}\n")

    parsed = translator.parse_material_analysis(response)
    f.write("\n=== 解析结果 ===\n")
    if parsed:
        f.write(json.dumps(parsed, ensure_ascii=False, indent=2))
    else:
        f.write("解析失败，返回 None")

print(f"响应已保存到 debug_output.txt")
print(f"响应长度: {len(response)} 字符")
