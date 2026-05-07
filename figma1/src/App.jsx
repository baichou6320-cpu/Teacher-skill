import { useEffect, useMemo, useRef, useState } from "react";

const API_URL = "/api/analyze";

const demoMaterial = `AI 安全基础学习材料

AI 安全关注的是如何让模型在复杂任务中保持有帮助、诚实和安全。模型对齐是核心问题：模型不仅要完成用户指令，还要理解人类意图、边界和长期影响。

越狱通常指用户通过特殊措辞绕过模型安全策略。提示注入则经常出现在外部材料、网页或文档中，它会伪装成更高优先级的指令，诱导 Agent 忽略原始任务。

评估不是只看模型答对多少题，而是要设计能暴露失败模式的任务。例如：模型是否会泄露敏感信息，是否会被恶意文本操控，是否会在不确定时编造答案。

风险缓解需要结合权限控制、输入过滤、工具调用审计、人工复核和复习计划。学习时最容易混淆的是：把越狱和提示注入当成同一种问题，或者只看直接答案而不做主动回忆。`;

const sessions = [
  {
    id: "#txA7F",
    name: "AI 安全基础",
    date: "2026-05-07",
    mode: "苏格拉底",
    task: "学习材料_001",
    material: demoMaterial,
  },
  {
    id: "#rxD42",
    name: "Transformer 笔记",
    date: "2026-05-06",
    mode: "追问",
    task: "论文笔记_014",
    material:
      "Transformer 使用注意力机制建模序列关系。自注意力可以让每个 token 关注其他 token，多头注意力能够从不同子空间捕捉信息。位置编码用于补充顺序信息，因为模型本身没有循环结构。",
  },
  {
    id: "#mkC19",
    name: "复习薄弱点",
    date: "2026-05-04",
    mode: "复习",
    task: "错题回顾_006",
    material:
      "今天复习时发现两个问题：第一，总是把直接答案当作理解；第二，无法清楚区分概念定义、应用场景和失败边界。需要用主动回忆重新测试。",
  },
];

const keywordBank = [
  {
    label: "模型对齐",
    aliases: ["alignment", "对齐", "人类意图", "价值", "安全训练"],
    question: "如果模型完成了字面指令，但违背了真实学习目标，这算不算对齐失败？为什么？",
    alert: "容易把“听话”误认为“对齐”，忽略边界和长期影响。",
  },
  {
    label: "越狱",
    aliases: ["jailbreak", "越狱", "绕过", "特殊措辞", "安全策略"],
    question: "为什么模型经过安全训练后，仍然可能被特殊措辞诱导输出不合适内容？",
    alert: "容易只记住攻击话术，而没有理解它在绕过哪一层约束。",
  },
  {
    label: "提示注入",
    aliases: ["prompt injection", "提示注入", "外部材料", "网页", "文档", "高优先级"],
    question: "提示注入和越狱最大的区别是什么？它为什么对 Agent 工具调用更危险？",
    alert: "容易把提示注入当作普通用户提问，忽略它来自被读取的外部内容。",
  },
  {
    label: "评估",
    aliases: ["evaluation", "评估", "测试", "失败模式", "暴露", "不确定"],
    question: "你会如何设计一道题，测试自己是否真正理解这个概念，而不是只会复述？",
    alert: "容易只看答对率，没有设计能暴露失败边界的测试。",
  },
  {
    label: "风险缓解",
    aliases: ["risk mitigation", "风险", "缓解", "权限", "审计", "人工复核", "过滤"],
    question: "如果要把这个知识点落到真实产品里，最小可行的风险控制是什么？",
    alert: "容易停留在原则层面，没有拆成可执行的权限、审计和复核动作。",
  },
  {
    label: "自注意力",
    aliases: ["self-attention", "自注意力", "注意力机制", "token", "序列关系"],
    question: "自注意力为什么能帮助模型理解不同 token 之间的关系？",
    alert: "容易只记公式，不清楚它到底在比较哪些信息。",
  },
  {
    label: "多头注意力",
    aliases: ["multi-head", "多头注意力", "不同子空间", "多头"],
    question: "多头注意力相比单个注意力头，多解决了什么表达问题？",
    alert: "容易把“多头”理解成简单重复，而不是不同视角的信息捕捉。",
  },
  {
    label: "位置编码",
    aliases: ["位置编码", "顺序信息", "循环结构", "位置"],
    question: "如果没有位置编码，Transformer 会在哪些任务上丢失关键信息？",
    alert: "容易忽略模型本身并不知道 token 的先后顺序。",
  },
  {
    label: "主动回忆",
    aliases: ["主动回忆", "闭卷", "复述", "复习", "错题", "薄弱点"],
    question: "为什么只看答案不等于真正理解？你会如何验证自己真的掌握？",
    alert: "容易把熟悉感当成掌握，缺少闭卷输出检验。",
  },
];

const toolGroups = [
  {
    label: "学习 Agent 工具",
    tools: ["概念提取器", "苏格拉底追问", "误区检测器", "直接答案模式", "复习计划器", "学习进度追踪"],
  },
  {
    label: "本地内容处理",
    tools: ["文本读取", "段落切分", "摘要生成", "知识卡片生成"],
  },
  {
    label: "输出工具",
    tools: ["学习卡片导出", "测验导出", "复习笔记导出"],
  },
];

const initialLogs = ["[就绪] 本地前端已启动", "[提示] 粘贴文本或上传 .txt/.md 后点击开始分析"];

function formatElapsed(totalSeconds) {
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function splitSentences(text) {
  return text
    .replace(/\s+/g, " ")
    .split(/[。！？.!?]\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildSummary(text) {
  const sentences = splitSentences(text);
  if (sentences.length === 0) return "还没有输入材料。";
  return sentences.slice(0, 2).join("。") + (sentences.length > 1 ? "。" : "");
}

function extractFallbackConcepts(text) {
  const normalized = text.replace(/[^\u4e00-\u9fa5a-zA-Z0-9\s]/g, " ");
  const words = normalized
    .split(/\s+/)
    .map((word) => word.trim())
    .filter((word) => word.length >= 2 && !["this", "that", "with", "from"].includes(word.toLowerCase()));

  const counts = new Map();
  words.forEach((word) => counts.set(word, (counts.get(word) || 0) + 1));

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label]) => ({
      label,
      source: "材料高频词",
      question: `请不用原文复述，解释“${label}”在这份材料里的作用。`,
      alert: `需要确认“${label}”的定义、例子和边界是否都能说清楚。`,
    }));
}

function analyzeMaterial(text) {
  const source = text.trim();
  const lowered = source.toLowerCase();
  const matched = keywordBank
    .filter((item) => item.aliases.some((alias) => lowered.includes(alias.toLowerCase())))
    .map((item) => ({ ...item, source: "命中材料关键词" }));

  const concepts = matched.length > 0 ? matched : extractFallbackConcepts(source);
  const safeConcepts =
    concepts.length > 0
      ? concepts.slice(0, 5)
      : [
          {
            label: "核心主题",
            source: "默认分析",
            question: "这份材料最想解决的核心问题是什么？",
            alert: "材料太短，建议补充更多上下文。",
          },
        ];

  const sentences = splitSentences(source);
  const needsReview = safeConcepts.slice(0, 2).map((item) => `用自己的话解释“${item.label}”，并举一个反例。`);

  if (/直接答案|答案|解释/.test(source)) {
    needsReview.push("避免只看解释：至少做一次闭卷主动回忆。");
  }

  return {
    summary: buildSummary(source),
    concepts: safeConcepts,
    questions: safeConcepts.slice(0, 3).map((item) => item.question),
    alerts: safeConcepts.slice(0, 3).map((item) => item.alert),
    needsReview: needsReview.slice(0, 3),
    reviewPlan: [
      "明天 09:30：闭卷写出 3 个核心概念的定义和边界。",
      "明天 14:00：回答一组追问，只允许看自己的草稿。",
      "明天 20:00：把薄弱点整理成 5 张复习卡片。",
    ],
    stats: {
      chars: source.length,
      paragraphs: source.split(/\n+/).filter((item) => item.trim()).length,
      sentences: sentences.length,
    },
  };
}

function normalizeApiResult(data) {
  const concepts = Array.isArray(data.concepts) && data.concepts.length > 0
    ? data.concepts
    : [{ label: data.title || "核心主题", source: data.source || "Teacher-skill", content: data.summary || "" }];

  return {
    summary: data.summary || "后端没有返回摘要。",
    concepts,
    questions: Array.isArray(data.questions) ? data.questions : [],
    alerts: Array.isArray(data.alerts) ? data.alerts : [],
    needsReview: Array.isArray(data.needsReview) ? data.needsReview : [],
    reviewPlan: Array.isArray(data.reviewPlan) ? data.reviewPlan : [],
    chunks: Array.isArray(data.chunks) ? data.chunks : [],
    source: data.source || "unknown",
    fallbackReason: data.fallbackReason || "",
    stats: data.stats || {
      chars: data.file?.chars || 0,
      paragraphs: 0,
      sentences: 0,
    },
  };
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",")[1] : value);
    };
    reader.onerror = () => reject(reader.error || new Error("文件读取失败"));
    reader.readAsDataURL(file);
  });
}

function Badge({ label, value, tone = "green" }) {
  const toneClass =
    tone === "warn"
      ? "border-amber-300/50 bg-amber-200/15 text-amber-100"
      : tone === "done"
        ? "border-emerald-300/50 bg-emerald-300/15 text-emerald-100"
        : "border-emerald-300/35 bg-emerald-300/10 text-emerald-100";

  return (
    <div className={`flex items-center gap-2 rounded-sm border px-2.5 py-1 ${toneClass}`}>
      <span className="text-[10px] uppercase tracking-[0.18em] text-emerald-100/55">{label}</span>
      <span className="text-[11px] font-semibold">{value}</span>
    </div>
  );
}

function SectionHeader({ eyebrow, title, right }) {
  return (
    <div className="mb-3 flex items-center justify-between border-b border-emerald-200/15 pb-2">
      <div>
        <div className="text-[10px] uppercase tracking-[0.28em] text-emerald-100/45">{eyebrow}</div>
        <div className="mt-1 text-[13px] font-semibold text-emerald-50">{title}</div>
      </div>
      {right}
    </div>
  );
}

function ResultCard({ title, children, tone = "green" }) {
  const toneClass =
    tone === "warn"
      ? "border-amber-200/35 bg-amber-100/10"
      : tone === "danger"
        ? "border-rose-300/35 bg-rose-200/10"
        : "border-emerald-200/25 bg-emerald-50/[0.06]";

  return (
    <div className={`panel-card ${toneClass} p-4`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[12px] font-semibold text-emerald-50">{title}</h3>
        <span className="text-[10px] text-emerald-100/40">本地生成</span>
      </div>
      {children}
    </div>
  );
}

function App() {
  const [activeSession, setActiveSession] = useState(sessions[0]);
  const [material, setMaterial] = useState(sessions[0].material);
  const [fileName, setFileName] = useState("内置示例材料");
  const [status, setStatus] = useState("待分析");
  const [mode, setMode] = useState("苏格拉底");
  const [score, setScore] = useState(72.5);
  const [elapsed, setElapsed] = useState(0);
  const [command, setCommand] = useState("");
  const [logs, setLogs] = useState(initialLogs);
  const [result, setResult] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [runtimeLabel, setRuntimeLabel] = useState("浏览器本地预览");
  const [directAnswer, setDirectAnswer] = useState(false);
  const [reviewModal, setReviewModal] = useState(false);
  const [selectedTool, setSelectedTool] = useState("概念提取器");
  const timeouts = useRef([]);

  const statusTone = status === "分析中" ? "warn" : status === "已完成" ? "done" : "green";
  const canRun = (uploadedFile || material.trim().length > 20) && status !== "分析中";

  const livePreview = useMemo(() => analyzeMaterial(material), [material]);
  const displayedResult = result || livePreview;
  const hasRunResult = Boolean(result) || directAnswer;

  useEffect(() => {
    const interval = window.setInterval(() => {
      setElapsed((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    return () => timeouts.current.forEach((timer) => window.clearTimeout(timer));
  }, []);

  function pushLog(delay, line) {
    const timer = window.setTimeout(() => {
      setLogs((items) => [...items, line]);
    }, delay);
    timeouts.current.push(timer);
  }

  async function handleExecute() {
    if (!canRun) return;

    timeouts.current.forEach((timer) => window.clearTimeout(timer));
    timeouts.current = [];
    setStatus("分析中");
    setScore(72.5);
    setResult(null);
    setDirectAnswer(false);
    setRuntimeLabel("连接 Python API");
    setLogs([`[开始] 发送材料到本地 Python API：${fileName}`]);

    pushLog(500, uploadedFile ? "[上传] 正在交给后端读取 PDF/txt/md" : "[上传] 正在交给后端分析粘贴文本");
    pushLog(1300, "[后端] 正在提取文本并调用 Teacher-skill 引擎");
    pushLog(2800, "[LLM] 如果配置可用，将返回真实知识点拆解结果");

    try {
      const controller = new AbortController();
      const abortTimer = window.setTimeout(() => controller.abort(), 45000);
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          text: uploadedFile ? "" : material,
          fileName,
          fileDataBase64: uploadedFile?.dataBase64 || "",
          mimeType: uploadedFile?.mimeType || "",
          userLevel: "beginner",
          useRealEngine: true,
        }),
      });
      window.clearTimeout(abortTimer);
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      const normalized = normalizeApiResult(data);
      setResult(normalized);
      if (data.extractedText) {
        setMaterial(data.extractedText);
      }
      setStatus("已完成");
      setScore(normalized.source === "teacher_skill_llm" ? 92.0 : 84.0);
      setRuntimeLabel(normalized.source === "teacher_skill_llm" ? "Teacher-skill LLM" : "后端 fallback");
      setLogs((items) => [
        ...items,
        normalized.source === "teacher_skill_llm"
          ? "[完成] 已打通本地 Python API，并调用 Teacher-skill 真实分析引擎"
          : `[降级] Python API 已返回，但真实引擎未成功：${normalized.fallbackReason}`,
      ]);
    } catch (error) {
      const fallback = analyzeMaterial(material);
      setResult({
        ...fallback,
        source: "browser_fallback",
        fallbackReason: error.message,
        chunks: [],
      });
      setStatus("已完成");
      setScore(70.0);
      setRuntimeLabel("浏览器 fallback");
      setLogs((items) => [
        ...items,
        `[失败] 未能连接本地 Python API：${error.message}`,
        "[提示] 请先启动：.venv\\Scripts\\python.exe api_server.py",
      ]);
    }
  }

  async function handleFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setStatus("待分析");
    setResult(null);
    setDirectAnswer(false);
    setRuntimeLabel("等待 Python API");

    if (file.name.toLowerCase().endsWith(".pdf")) {
      const dataBase64 = await readFileAsBase64(file);
      setUploadedFile({ name: file.name, mimeType: file.type || "application/pdf", dataBase64 });
      setMaterial("");
      setLogs([`[文件] 已选择 PDF：${file.name}`, "[提示] 点击开始分析后，后端会用 pypdf 提取文本并调用 Teacher-skill"]);
      return;
    }

    const text = await file.text();
    setUploadedFile(null);
    setMaterial(text);
    setLogs([`[文件] 已读取 ${file.name}`, "[提示] 点击开始分析后，文本会发送到本地 Python API"]);
  }

  function handleToolClick(tool) {
    setSelectedTool(tool);

    if (tool === "直接答案模式") {
      setMode("直接答案");
      setDirectAnswer(true);
      setResult((current) => current || analyzeMaterial(material));
      setStatus("已完成");
      setLogs((items) => [...items, "[工具] 已切换到直接答案模式"]);
    }

    if (tool === "复习计划器") {
      setReviewModal(true);
      setLogs((items) => [...items, "[工具] 已打开明日复习计划"]);
    }
  }

  function handleSessionClick(session) {
    setActiveSession(session);
    setMaterial(session.material);
    setFileName(`${session.name}.txt`);
    setUploadedFile(null);
    setMode(session.mode);
    setStatus("待分析");
    setScore(72.5);
    setResult(null);
    setDirectAnswer(false);
    setRuntimeLabel("浏览器本地预览");
    setLogs([`[历史] 已载入 ${session.name}`, "[提示] 当前材料已放入左侧输入区"]);
  }

  return (
    <main className="scanline-overlay min-h-screen bg-[#0d1712] text-emerald-50">
      <div className="grid h-screen grid-rows-[44px_1fr_56px] overflow-hidden">
        <header className="grid grid-cols-[220px_1fr_320px] border-b border-emerald-200/15 bg-[#102018]/95">
          <div className="flex items-center border-r border-emerald-200/15 px-4">
            <span className="text-sm font-black tracking-[0.18em] text-emerald-100"># TEACHER-ELF</span>
          </div>
          <div className="flex min-w-0 items-center gap-2 overflow-hidden px-3">
            <Badge label="会话" value={activeSession.id} />
            <Badge label="任务" value={activeSession.task} />
            <Badge label="模式" value={mode} />
            <Badge label="状态" value={status} tone={statusTone} />
            <Badge label="运行" value={runtimeLabel} />
          </div>
          <div className="flex items-center justify-end gap-2 border-l border-emerald-200/15 px-3">
            <Badge label="用时" value={formatElapsed(elapsed)} />
            <Badge label="掌握度" value={score.toFixed(1)} tone={score >= 84 ? "done" : "warn"} />
          </div>
        </header>

        <div className="grid min-h-0 grid-cols-[220px_1fr_310px]">
          <aside className="panel-shell min-h-0 border-l-0 border-t-0 border-b-0 p-3">
            <SectionHeader eyebrow="Step 0" title="学习历史" right={<span className="text-[10px] text-emerald-100/45">LOCAL</span>} />
            <button
              className="mb-3 w-full rounded-sm border border-emerald-300/35 bg-emerald-300/10 px-3 py-2 text-left text-[12px] font-semibold text-emerald-50 transition hover:bg-emerald-300/15"
              onClick={() => handleSessionClick(sessions[0])}
            >
              新建演示会话 <span className="float-right">+</span>
            </button>
            <div className="space-y-2">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  className={`w-full rounded-sm border px-3 py-2 text-left transition ${
                    activeSession.id === session.id
                      ? "border-emerald-300/50 bg-emerald-200/15 text-emerald-50"
                      : "border-emerald-200/12 bg-emerald-950/15 text-emerald-100/60 hover:border-emerald-200/30 hover:text-emerald-50"
                  }`}
                  onClick={() => handleSessionClick(session)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[12px] font-semibold">{session.name}</span>
                    <span className="text-[10px]">{session.mode}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px] text-emerald-100/38">
                    <span>{session.id}</span>
                    <span>{session.date}</span>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          <section className="relative min-h-0 overflow-hidden border-r border-emerald-200/15 bg-[#0f1b15]">
            <div className="workspace-grid absolute inset-0 opacity-70" />
            <div className="relative z-10 grid h-full grid-rows-[84px_1fr] gap-3 p-3">
              <div className="panel-card flex items-center justify-between p-4">
                <div className="min-w-0">
                  <div className="text-[10px] uppercase tracking-[0.24em] text-emerald-100/45">当前材料</div>
                  <div className="mt-2 truncate text-[14px] font-semibold text-emerald-50">{fileName}</div>
                  <div className="mt-1 text-[11px] text-emerald-100/45">
                    {displayedResult.stats.chars} 字符 / {displayedResult.stats.paragraphs} 段落 / {runtimeLabel}
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <Metric label="概念" value={displayedResult.concepts.length} />
                  <Metric label="追问" value={displayedResult.questions.length} />
                  <Metric label="复习" value={displayedResult.needsReview.length} />
                </div>
              </div>

              <div className="grid min-h-0 grid-cols-[360px_1fr_250px] gap-3">
                <div className="panel-card min-h-0 p-4">
                  <SectionHeader eyebrow="Step 1" title="导入本地材料" />
                  <textarea
                    className="thin-scroll h-[calc(100%-136px)] w-full resize-none rounded-sm border border-emerald-200/20 bg-[#f6fff7]/95 p-3 text-[12px] leading-6 text-slate-900 outline-none placeholder:text-slate-400 focus:border-emerald-400"
                    value={material}
                    onChange={(event) => {
                      setMaterial(event.target.value);
                      setUploadedFile(null);
                      setStatus("待分析");
                      setResult(null);
                      setRuntimeLabel("浏览器本地预览");
                    }}
                    placeholder="把学习材料粘贴到这里，或上传 PDF / txt / md 文件。PDF 会交给本地 Python 后端提取文本。"
                  />
                  <div className="mt-3 grid grid-cols-[1fr_120px] gap-2">
                    <label className="flex cursor-pointer items-center justify-center rounded-sm border border-emerald-300/35 bg-emerald-200/10 px-3 py-2 text-[12px] text-emerald-50 transition hover:bg-emerald-200/15">
                      上传 PDF/txt/md
                      <input className="hidden" type="file" accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown" onChange={handleFile} />
                    </label>
                    <button
                      className="rounded-sm border border-emerald-300/45 bg-emerald-300/20 px-3 py-2 text-[12px] font-semibold text-emerald-50 transition hover:bg-emerald-300/25 disabled:cursor-not-allowed disabled:opacity-40"
                      disabled={!canRun}
                      onClick={handleExecute}
                    >
                      开始分析
                    </button>
                  </div>
                </div>

                <div className="panel-card min-h-0 overflow-hidden p-4">
                  {status === "分析中" ? (
                    <div className="h-full">
                      <div className="mb-4 flex items-center gap-3">
                        <span className="status-pulse h-2.5 w-2.5 rounded-full bg-amber-200" />
                        <span className="text-[12px] font-semibold tracking-[0.2em] text-amber-100">正在本地分析</span>
                      </div>
                      <div className="loading-bar mb-4 h-2 rounded-sm border border-amber-200/30 bg-amber-100/10" />
                      <TerminalLogs logs={logs} />
                    </div>
                  ) : hasRunResult ? (
                    <div className="thin-scroll grid max-h-full gap-3 overflow-y-auto pr-2">
                      <ResultCard title="材料摘要">
                        <p className="text-[12px] leading-6 text-emerald-50/80">{displayedResult.summary}</p>
                      </ResultCard>

                      <ResultCard title="关键概念">
                        <div className="flex flex-wrap gap-2">
                          {displayedResult.concepts.map((item) => (
                            <span key={item.label} className="rounded-sm border border-emerald-300/30 bg-emerald-300/10 px-2.5 py-1.5 text-[12px] text-emerald-50">
                              {item.label}
                            </span>
                          ))}
                        </div>
                      </ResultCard>

                      <ResultCard title="苏格拉底追问">
                        <ol className="space-y-2 text-[12px] leading-6 text-emerald-50/80">
                          {displayedResult.questions.map((item, index) => (
                            <li key={item}>
                              <span className="text-emerald-200">{String(index + 1).padStart(2, "0")}</span> {item}
                            </li>
                          ))}
                        </ol>
                      </ResultCard>

                      <div className="grid grid-cols-2 gap-3">
                        <ResultCard title="误区提醒" tone="danger">
                          <ul className="space-y-2 text-[12px] leading-6 text-rose-50/85">
                            {displayedResult.alerts.map((item) => (
                              <li key={item}>! {item}</li>
                            ))}
                          </ul>
                        </ResultCard>
                        <ResultCard title="待复习项" tone="warn">
                          <ul className="space-y-2 text-[12px] leading-6 text-amber-50/85">
                            {displayedResult.needsReview.map((item) => (
                              <li key={item}>- {item}</li>
                            ))}
                          </ul>
                        </ResultCard>
                      </div>

                      {directAnswer ? (
                        <ResultCard title="直接答案模式" tone="warn">
                          <p className="text-[12px] leading-6 text-amber-50/85">
                            这份材料的核心是：{displayedResult.concepts[0]?.label || "核心主题"}。建议先用自己的话解释它，再用一个例子和一个反例确认边界。
                          </p>
                        </ResultCard>
                      ) : null}
                    </div>
                  ) : (
                    <div className="flex h-full items-center justify-center">
                      <div className="max-w-2xl text-center">
                        <div className="mx-auto mb-5 h-2 w-72 rounded-sm border border-emerald-200/20 bg-emerald-50/[0.06]" />
                        <div className="text-[12px] font-semibold tracking-[0.24em] text-emerald-100/55">等待本地分析</div>
                        <p className="mt-4 text-[13px] leading-7 text-emerald-50/72">
                          当前材料会在浏览器本地处理。点击左侧“开始分析”后，系统会按材料内容生成摘要、概念、追问、误区和复习计划。
                        </p>
                        <div className="mt-5 grid grid-cols-3 gap-3 text-left">
                          <MiniStep title="01 导入" body="粘贴文本或上传 txt/md" />
                          <MiniStep title="02 分析" body="本地规则提取概念" />
                          <MiniStep title="03 复习" body="生成追问和计划" />
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="panel-card min-h-0 p-3">
                  <SectionHeader eyebrow="Step 2" title="运行日志" />
                  <TerminalLogs logs={logs} compact />
                  <div className="mt-4 border-t border-emerald-200/15 pt-3">
                    <div className="mb-2 text-[10px] uppercase tracking-[0.24em] text-emerald-100/45">当前工具</div>
                    <div className="rounded-sm border border-emerald-300/25 bg-emerald-300/10 px-2 py-2 text-[12px] text-emerald-50">
                      {selectedTool}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <aside className="panel-shell min-h-0 border-r-0 border-t-0 border-b-0 p-3">
            <SectionHeader eyebrow="Step 3" title="工具目录" right={<span className="text-[10px] text-emerald-100/45">可点击</span>} />
            <div className="thin-scroll max-h-[calc(100vh-112px)] space-y-3 overflow-y-auto pr-1">
              {toolGroups.map((group) => (
                <div key={group.label} className="rounded-sm border border-emerald-200/14 bg-emerald-950/20 p-2.5">
                  <div className="mb-2 text-[11px] font-semibold text-emerald-100/60">{group.label}</div>
                  <div className="space-y-1.5">
                    {group.tools.map((tool) => (
                      <button
                        key={tool}
                        className={`w-full rounded-sm border px-2.5 py-2 text-left text-[12px] transition ${
                          selectedTool === tool
                            ? "border-emerald-300/50 bg-emerald-200/15 text-emerald-50"
                            : "border-emerald-200/12 bg-[#102018] text-emerald-100/58 hover:border-emerald-200/30 hover:text-emerald-50"
                        }`}
                        onClick={() => handleToolClick(tool)}
                      >
                        + {tool}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </aside>
        </div>

        <footer className="grid grid-cols-[1fr_170px] border-t border-emerald-200/15 bg-[#102018]">
          <input
            className="border-0 bg-transparent px-4 text-[12px] text-emerald-50 outline-none placeholder:text-emerald-100/35"
            placeholder="输入命令，例如：分析这份材料 / 生成复习计划 / 直接解释第一个概念..."
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") handleExecute();
            }}
          />
          <button
            className="border-l border-emerald-200/15 bg-emerald-300/15 text-[12px] font-semibold tracking-[0.22em] text-emerald-50 transition hover:bg-emerald-300/22 disabled:opacity-40"
            disabled={!canRun}
            onClick={handleExecute}
          >
            执行
          </button>
        </footer>
      </div>

      {reviewModal ? <ReviewModal result={displayedResult} onClose={() => setReviewModal(false)} /> : null}
    </main>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-sm border border-emerald-200/15 bg-emerald-50/[0.06] px-3 py-2">
      <div className="text-[16px] font-black text-emerald-50">{value}</div>
      <div className="mt-0.5 text-[10px] text-emerald-100/45">{label}</div>
    </div>
  );
}

function MiniStep({ title, body }) {
  return (
    <div className="rounded-sm border border-emerald-200/15 bg-emerald-50/[0.06] p-3">
      <div className="text-[11px] font-semibold text-emerald-100">{title}</div>
      <div className="mt-2 text-[11px] leading-5 text-emerald-50/58">{body}</div>
    </div>
  );
}

function TerminalLogs({ logs, compact = false }) {
  return (
    <div className={`thin-scroll overflow-y-auto rounded-sm border border-emerald-200/15 bg-[#09120d]/70 p-3 ${compact ? "h-[260px]" : "h-[calc(100%-44px)]"}`}>
      <div className="space-y-2 text-[11px] leading-5 text-emerald-100/58">
        {logs.map((line, index) => (
          <div key={`${line}-${index}`} className="flex gap-2">
            <span className="text-emerald-200/70">{String(index + 1).padStart(2, "0")}</span>
            <span className={line.includes("完成") ? "text-emerald-100" : ""}>{line}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReviewModal({ result, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#07100b]/72 p-4 backdrop-blur-sm">
      <div className="w-[560px] rounded-sm border border-emerald-200/30 bg-[#13231a] p-5 shadow-glow">
        <div className="mb-4 flex items-center justify-between border-b border-emerald-200/15 pb-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.26em] text-emerald-100/45">Review Scheduler</div>
            <h2 className="mt-1 text-base font-bold text-emerald-50">明日复习计划</h2>
          </div>
          <button className="text-xs text-emerald-100/55 hover:text-emerald-50" onClick={onClose}>
            关闭
          </button>
        </div>
        <div className="space-y-3 text-[12px] leading-6 text-emerald-50/82">
          {result.reviewPlan.map((item, index) => (
            <div key={item} className="rounded-sm border border-emerald-200/15 bg-emerald-50/[0.06] p-3">
              <span className="font-semibold text-emerald-200">T+{index + 1}</span> {item}
            </div>
          ))}
        </div>
        <button className="mt-4 w-full rounded-sm border border-emerald-300/35 bg-emerald-300/15 py-2 text-[12px] font-semibold tracking-[0.2em] text-emerald-50 hover:bg-emerald-300/22" onClick={onClose}>
          确认计划
        </button>
      </div>
    </div>
  );
}

export default App;
