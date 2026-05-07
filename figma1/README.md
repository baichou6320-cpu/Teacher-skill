# TEACHER-ELF figma1

这是 Teacher-skill 的本地前端演示原型：React + Tailwind CSS，中文界面。

它已经接入项目根目录的 `api_server.py` 本地 API。你可以直接粘贴学习材料，或上传 `.pdf` / `.txt` / `.md` 文件：

- 材料摘要
- 关键概念提取
- 苏格拉底追问
- 误区提醒
- 待复习项
- 明日复习计划

## 本地运行

先在项目根目录启动 Python API：

```bash
cd ..
.venv\Scripts\python.exe api_server.py
```

再启动前端：

```bash
cd figma1
npm install
npm run dev
```

打开终端里显示的地址，通常是：

```text
http://127.0.0.1:5173/
```

## 演示步骤

1. 打开页面，确认左侧材料输入区已有示例内容。
2. 粘贴一段自己的学习材料，或上传 `.txt` / `.md` 文件。
3. 也可以上传 `.pdf` 文件，后端会用 `pypdf` 提取文本。
4. 点击 `开始分析`，前端会调用 `http://127.0.0.1:8765/api/analyze`。
5. 如果 LLM 可用，结果来源显示 `Teacher-skill LLM`。
6. 如果外部模型超时或失败，会自动显示 `后端 fallback`，保证演示不中断。
7. 点击右侧 `直接答案模式`，展示快速解释。
8. 点击右侧 `复习计划器`，打开明日复习弹窗。

## 当前边界

- PDF 解析已经走 Python 后端和 `pypdf`。
- 前端已经通过本地 API 接入 Teacher-skill 的 `TutorEngine.analyze_material()`。
- 真实 LLM 路径最多等待 25 秒；超时会返回后端 fallback。
- 当前还没有做完整的问答判卷闭环前端，只完成“材料上传 -> 分析拆解 -> 展示结果”。
