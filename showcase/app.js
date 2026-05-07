const ANALYZE_API_URL = "/api/analyze";
const TEACH_API_URL = "/api/teach";
const JUDGE_API_URL = "/api/judge";
const HINT_API_URL = "/api/hint";
const RESPOND_API_URL = "/api/respond";
const DEMO_API_URL = "/api/demo";

const demoMaterial =
  "Transformer 是一种基于注意力机制的深度学习架构。它抛弃了 RNN 的逐步循环计算，用自注意力一次性建模序列中不同 token 之间的关系。由于没有天然的顺序结构，Transformer 需要位置编码告诉模型每个 token 在序列中的位置。多头注意力会并行学习多组关系，让模型同时捕捉语义、语法和长距离依赖。";

const recordingDemoFallback = {
  fileName: "录屏示例-番茄工作法.md",
  goal: "帮我理解番茄工作法为什么能提升专注",
  material:
    "番茄工作法是一种简单的时间管理方法。它把工作切成 25 分钟专注和 5 分钟休息的循环，帮助学习者降低启动难度、减少分心，并在休息中恢复注意力。",
  suggestedQuestion: "不太能，可以直接跟我说这个概念。",
  cards: [
    {
      id: "recording_card_1",
      title: "番茄工作法",
      content: "番茄工作法把工作拆成短时间专注周期，让任务更容易开始和推进。",
      difficulty: "easy",
      question: "请用自己的话解释番茄工作法为什么能降低开始任务的难度。",
      answer: "它把大任务切成 25 分钟左右的小周期，让人只需要先开始一个短时间段，而不是一次完成整个大任务。",
      analogy: "像先跑一小段热身路，而不是一开始就要求自己跑完整场马拉松。",
      status: "学习中",
    },
    {
      id: "recording_card_2",
      title: "25 分钟专注",
      content: "25 分钟专注周期要求用户在一个短时间窗口里只处理一个明确任务。",
      difficulty: "medium",
      question: "为什么一次只做一件事能帮助减少分心？",
      answer: "因为明确时间窗口和任务边界后，用户更容易拒绝消息、切换和临时打断。",
      analogy: "像给注意力设一个临时围栏，先保护这一小段时间不被打断。",
      status: "未开始",
    },
    {
      id: "recording_card_3",
      title: "休息恢复",
      content: "短休息不是浪费时间，而是恢复注意力、降低疲劳的重要组成部分。",
      difficulty: "easy",
      question: "为什么休息也属于学习或工作的有效环节？",
      answer: "因为持续专注会消耗注意力，短休息能帮助大脑恢复，让下一轮专注更稳定。",
      analogy: "像手机短暂充电，目的是让下一段使用更稳定。",
      status: "未开始",
    },
  ],
};

const appState = {
  step: 0,
  activeCard: 0,
  runtime: "等待资料",
  learningStyle: "苏格拉底",
  learningGoal: "",
  demoMode: false,
  demoData: null,
  sources: [],
  chatMessages: [],
  isThinking: false,
  isAnalyzing: false,
  mastered: new Set(),
  review: new Set(),
  cards: [],
};

const sourceUpload = document.querySelector("#sourceUpload");
const sourceList = document.querySelector("#sourceList");
const sourceCountLabel = document.querySelector("#sourceCountLabel");
const knowledgeList = document.querySelector("#knowledgeList");
const dialogueBox = document.querySelector("#dialogueBox");
const answerInput = document.querySelector("#answerInput");
const submitAnswer = document.querySelector("#submitAnswer");
const directAnswer = document.querySelector("#directAnswer");
const masteredMetric = document.querySelector("#masteredMetric");
const reviewMetric = document.querySelector("#reviewMetric");
const rateMetric = document.querySelector("#rateMetric");
const reportTimeline = document.querySelector("#reportTimeline");
const runtimeStatus = document.querySelector("#runtimeStatus");
const demoResetButton = document.querySelector("#demoResetButton");
const activeTopicLabel = document.querySelector("#activeTopicLabel");
const cardCountLabel = document.querySelector("#cardCountLabel");
const currentStageLabel = document.querySelector("#currentStageLabel");
const progressText = document.querySelector("#progressText");
const progressBar = document.querySelector("#progressBar");
const currentCardLabel = document.querySelector("#currentCardLabel");
const sourceUsedLabel = document.querySelector("#sourceUsedLabel");
const learningGoalLabel = document.querySelector("#learningGoalLabel");
const nextActionLabel = document.querySelector("#nextActionLabel");
const stageItems = [...document.querySelectorAll(".stage-item")];
const styleOptions = [...document.querySelectorAll(".style-option")];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function createId(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function addMessage(type, text, meta = "", extra = {}) {
  const message = {
    id: createId("msg"),
    type,
    text,
    meta,
    ...extra,
  };
  appState.chatMessages.push(message);
  return message;
}

function resetChat() {
  appState.chatMessages = [];
  appState.isThinking = false;
}

function resetLearningResult() {
  appState.cards = [];
  appState.activeCard = 0;
  appState.mastered.clear();
  appState.review.clear();
}

function setWaitingForGoal() {
  appState.learningGoal = "";
  appState.runtime = activeSources().length > 0 ? "等待学习目标" : "等待资料";
  appState.step = activeSources().length > 0 ? 1 : 0;
}

function clearStaleCardsAfterSourceChange() {
  if (appState.cards.length === 0) return;
  resetLearningResult();
  setWaitingForGoal();
  addMessage("system", "资料范围已变化，旧知识卡片已清空。请重新说明这次想学习什么。", "资料更新");
}

function looksLikeMaterial(text) {
  const hasLongLength = text.length >= 120;
  const hasParagraphBreak = /\n\s*\n/.test(text);
  const hasStudyCommand = /^(我想|帮我|开始|学习|讲讲|解释|总结|生成|出题|复习)/.test(text);
  return !hasStudyCommand && (hasLongLength || hasParagraphBreak);
}

function classifyLearningInput(text, card = null) {
  const value = text.trim();
  if (!value) return "empty";
  const directAnswerPattern = /(速查|直接.*答案|给.*答案|告诉我.*答案|答案是什么|正确答案|标准答案|看答案)/;
  if (directAnswerPattern.test(value)) return "direct_answer";

  const answerCuePattern = /(是一种|是一个|可以理解为|类似|相当于|通过|用于|用来|因为|所以|能够|帮助|组成|基于|属于|解决|适合|边界|例子)/;
  if (value.length >= 10 && answerCuePattern.test(value)) return "answer";

  const title = card?.title || "";
  if (title && value.toLowerCase().includes(title.toLowerCase()) && value.length >= title.length + 8) {
    return "answer";
  }

  const explanationPattern =
    /(不懂|不太懂|不太能|不太会|不理解|不会|答不上来|没懂|看不懂|直接讲|直接说|直接跟我说|直接告诉我|跟我说这个概念|说这个概念|告诉我这个概念|可以直接|详细.*说|详细.*讲|解释|讲解|定义|是什么|什么意思|从头讲|教我|帮我理解|直接学习|先学习|展开说)/;
  if (explanationPattern.test(value)) return "explain";

  return "answer";
}

function sourceKindFromFile(file) {
  const name = file.name.toLowerCase();
  if (name.endsWith(".pdf")) return "pdf";
  if (name.endsWith(".md") || name.endsWith(".markdown")) return "md";
  return "txt";
}

function sourceKindLabel(source) {
  if (source.kind === "pdf") return "PDF";
  if (source.kind === "md") return "MD";
  return "TXT";
}

function sourceSizeLabel(source) {
  if (source.kind === "pdf") return "PDF 文件";
  return `${source.text.trim().length} 字符`;
}

function activeSources() {
  return appState.sources.filter((source) => source.enabled);
}

function activeTextSources() {
  return activeSources().filter((source) => source.kind !== "pdf");
}

function statusValue(card) {
  if (card.status === "已掌握") return "mastered";
  if (card.status === "待巩固") return "needs_review";
  if (card.status === "学习中") return "in_progress";
  return "not_started";
}

function cardPayload(card, extra = {}) {
  return {
    useRealEngine: !appState.demoMode,
    learningGoal: appState.learningGoal,
    learningStyle: appState.learningStyle,
    cardIndex: appState.activeCard,
    totalCards: appState.cards.length,
    card: {
      id: card.id,
      title: card.title,
      content: card.content || card.answer,
      question: card.question,
      answer: card.answer,
      correctAnswer: card.answer,
      options: card.options || null,
      analogy: card.analogy || "",
      difficulty: card.difficulty,
      status: card.status,
      statusValue: statusValue(card),
      hintLevel: card.hintLevel || 0,
      failCount: card.failCount || 0,
      attempts: card.attempts || 0,
    },
    ...extra,
  };
}

function applyCardApiState(card, data) {
  if (data.question) card.question = data.question;
  if (data.correctAnswer) card.answer = data.correctAnswer;
  if (data.options) card.options = data.options;
  if (data.card) {
    if (Number.isFinite(Number(data.card.hintLevel))) card.hintLevel = Number(data.card.hintLevel);
    if (Number.isFinite(Number(data.card.failCount))) card.failCount = Number(data.card.failCount);
    if (Number.isFinite(Number(data.card.attempts))) card.attempts = Number(data.card.attempts);
  }
}

function splitWords(text) {
  return text
    .replace(/[^\u4e00-\u9fa5A-Za-z0-9\s]/g, " ")
    .split(/\s+/)
    .map((word) => word.trim())
    .filter((word) => word.length >= 2);
}

function localCardsFromMaterial(text) {
  const labels = [...new Set(splitWords(text))].slice(0, 5);
  const safeLabels = labels.length > 0 ? labels : ["核心主题"];
  return safeLabels.map((label, index) => ({
    id: createId("card"),
    title: label,
    content: `“${label}”是这份材料中需要确认定义、作用和边界的知识点。`,
    difficulty: index === 0 ? "medium" : "easy",
    question: `请用自己的话解释“${label}”在这份材料里的作用。`,
    answer: `先说明“${label}”的定义，再补一个例子和一个反例。`,
    options: null,
    analogy: "",
    hintLevel: 0,
    failCount: 0,
    attempts: 0,
    status: index === 0 ? "学习中" : "未开始",
  }));
}

function cardsFromDemoData(data) {
  const cards = Array.isArray(data.cards) && data.cards.length > 0 ? data.cards : recordingDemoFallback.cards;
  return cards.map((card, index) => ({
    id: card.id || createId("demo_card"),
    title: card.title || `演示卡片 ${index + 1}`,
    content: card.content || card.answer || "",
    difficulty: card.difficulty || "easy",
    question: card.question || `请用自己的话解释“${card.title || `演示卡片 ${index + 1}`}”。`,
    answer: card.answer || card.content || "说明这个知识点的定义、作用和边界。",
    options: card.options || null,
    analogy: card.analogy || "",
    hintLevel: 0,
    failCount: 0,
    attempts: 0,
    status: index === 0 ? "学习中" : "未开始",
  }));
}

function cardsFromApiResult(data) {
  const chunks = Array.isArray(data.chunks) ? data.chunks : [];
  const concepts = Array.isArray(data.concepts) ? data.concepts : [];
  const questions = Array.isArray(data.questions) ? data.questions : [];
  const sourceItems = chunks.length > 0 ? chunks : concepts;

  return sourceItems.slice(0, 6).map((item, index) => ({
    id: item.id || item.chunk_id || createId("card"),
    title: item.title || item.label || `知识点 ${index + 1}`,
    content: item.content || item.answer || "",
    difficulty: item.difficulty || "medium",
    question:
      item.question ||
      questions[index] ||
      `请用自己的话解释“${item.title || item.label || `知识点 ${index + 1}`}”。`,
    answer:
      item.answer ||
      item.correct_answer ||
      item.content ||
      "说明这个概念的定义、例子和边界。",
    options: item.options || null,
    analogy: item.analogy || "",
    hintLevel: 0,
    failCount: 0,
    attempts: 0,
    status: index === 0 ? "学习中" : "未开始",
  }));
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

function addTextSource(name, text, kind = "txt") {
  const trimmed = text.trim();
  if (!trimmed) return null;
  const source = {
    id: createId("source"),
    name,
    kind,
    text: trimmed,
    enabled: true,
  };
  appState.sources.push(source);
  appState.runtime = "资料已就绪";
  appState.step = 1;
  addMessage("system", `已保存资料：${name}`, "Sources");
  return source;
}

async function addFileSource(file) {
  const kind = sourceKindFromFile(file);
  if (kind === "pdf") {
    const source = {
      id: createId("source"),
      name: file.name,
      kind,
      dataBase64: await readFileAsBase64(file),
      mimeType: file.type || "application/pdf",
      text: "",
      enabled: true,
    };
    appState.sources.push(source);
    appState.runtime = "资料已就绪";
    appState.step = 1;
    addMessage("system", `已上传 PDF：${file.name}`, "Sources");
    return source;
  }

  const text = await file.text();
  return addTextSource(file.name, text, kind);
}

function combinedTextFromSources(sources) {
  return sources
    .map((source, index) => `# 资料 ${index + 1}：${source.name}\n\n${source.text}`)
    .join("\n\n---\n\n");
}

function stageTitle() {
  return ["添加资料", "说明目标", "生成卡片", "问答复习"][appState.step] || "学习中";
}

function completionRate() {
  if (appState.cards.length === 0) return 0;
  return Math.round(((appState.mastered.size + appState.review.size) / appState.cards.length) * 100);
}

function nextActionText() {
  if (appState.sources.length === 0) {
    return "先上传 txt/md/pdf，或在中间粘贴一段材料并发送。";
  }
  if (appState.isAnalyzing) return "正在根据你的目标拆解资料，请稍等。";
  if (appState.cards.length === 0) return "资料已就绪。请在中间说：我想学什么，或直接输入“开始学习”。";
  if (appState.step === 3) return "在中间回答当前验证问题，或点击速查；也可以点知识卡片切换学习。";
  return "继续按中间对话推进学习。";
}

function renderSources() {
  sourceCountLabel.textContent = String(appState.sources.length);

  if (appState.sources.length === 0) {
    sourceList.innerHTML = `
      <div class="sources-empty-state">
        <div class="empty-icon">▤</div>
        <strong>Saved sources will appear here</strong>
        <span>点击 Add sources 上传 txt、md、pdf；也可以直接在中间对话框粘贴资料。</span>
      </div>
    `;
    return;
  }

  sourceList.innerHTML = appState.sources
    .map(
      (source) => `
        <article class="source-item" data-id="${source.id}">
          <div class="source-item-main">
            <label class="source-toggle" title="是否作为学习资料">
              <input class="source-enable" type="checkbox" data-id="${source.id}" ${source.enabled ? "checked" : ""}>
            </label>
            <div>
              <span class="source-title">${escapeHtml(source.name)}</span>
              <span class="source-detail">
                ${sourceKindLabel(source)} · ${sourceSizeLabel(source)} · ${source.enabled ? "用于学习" : "暂不使用"}
              </span>
            </div>
          </div>
          <div class="source-actions">
            <button class="source-action-button" data-action="rename" data-id="${source.id}">重命名</button>
            <button class="source-action-button danger" data-action="delete" data-id="${source.id}">删除</button>
          </div>
        </article>
      `
    )
    .join("");
}

function renderStages() {
  stageItems.forEach((item, index) => {
    item.classList.toggle("is-active", index === appState.step);
  });
}

function currentCardStatus(index, card) {
  if (appState.mastered.has(index)) return "已掌握";
  if (appState.review.has(index)) return "待巩固";
  return card.status;
}

function renderCards() {
  cardCountLabel.textContent = `${appState.cards.length} 张卡片`;
  knowledgeList.innerHTML = "";

  if (appState.cards.length === 0) {
    knowledgeList.innerHTML = `
      <div class="source-empty">
        资料上传后不会自动分析。等你在中间说明学习目标后，这里会显示拆解出的知识卡片。
      </div>
    `;
    return;
  }

  appState.cards.forEach((card, index) => {
    const item = document.createElement("button");
    item.className = `knowledge-card${index === appState.activeCard ? " is-active" : ""}`;
    item.type = "button";
    item.innerHTML = `
      <div class="card-title-row">
        <strong>${index + 1}. ${escapeHtml(card.title)}</strong>
        <span>${escapeHtml(card.difficulty)}</span>
      </div>
      <p>${escapeHtml(card.question)}</p>
      <div class="card-status">${escapeHtml(currentCardStatus(index, card))}</div>
    `;
    item.addEventListener("click", () => {
      openKnowledgeCard(index);
    });
    knowledgeList.appendChild(item);
  });
}

function renderMessage(message) {
  const meta = message.meta
    ? `<div class="message-meta">${escapeHtml(message.meta)}</div>`
    : "";
  const actions = Array.isArray(message.actions)
    ? `
      <div class="message-actions">
        ${message.actions
          .map(
            (action, index) => `
              <button
                class="message-action-button${message.resolved && action.selected ? " is-selected" : ""}"
                type="button"
                data-chat-action="${escapeHtml(action.action || "explain-mode")}"
                data-message-id="${escapeHtml(message.id)}"
                data-action-index="${index}"
                ${message.resolved ? "disabled" : ""}
              >
                <strong>${escapeHtml(action.label)}</strong>
                <span>${escapeHtml(action.description)}</span>
              </button>
            `
          )
          .join("")}
      </div>
    `
    : "";
  return `
    <div class="bubble ${escapeHtml(message.type)}">
      ${meta}
      <div>${escapeHtml(message.text)}</div>
      ${actions}
    </div>
  `;
}

function renderThinking() {
  if (!appState.isThinking) return "";
  return `
    <div class="bubble ai thinking-bubble">
      <div class="message-meta">Teacher-skill 正在处理</div>
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>
  `;
}

function renderDialogue() {
  activeTopicLabel.textContent =
    appState.cards[appState.activeCard]?.title ||
    (activeSources().length > 0 ? "等待学习目标" : "等待资料");
  if (appState.chatMessages.length === 0) {
    dialogueBox.innerHTML = `
      <div class="chat-empty-card">
        <strong>先给资料，再说目标</strong>
        <span>上传文件后不会立刻分析。你可以在这里说“我想学习 XGBoost 的核心原理”，我再根据选中的资料生成卡片并开始问答。</span>
      </div>
    `;
    return;
  }

  dialogueBox.innerHTML =
    appState.chatMessages.map(renderMessage).join("") + renderThinking();
  dialogueBox.scrollTop = dialogueBox.scrollHeight;
}

function progressiveTeachOptionsFromRequest(request) {
  if (classifyLearningInput(request || "") !== "explain") return {};
  if (/(不太能|不太会|答不上来|直接讲|直接说|直接跟我说|直接告诉我|跟我说这个概念|说这个概念|告诉我这个概念|可以直接)/.test(request || "")) {
    return {
      userRequest: request,
      supportMode: "direct_explain",
    };
  }
  return {
    userRequest: request,
    supportMode: "progressive_explain",
  };
}

function addExplainModeChoice(card, userRequest) {
  appState.runtime = "选择讲解方式";
  addMessage("ai", `你想用哪种方式学习“${card.title}”？`, "选择讲解方式", {
    actions: [
      {
        label: "引导我理解",
        description: "先拆成小步骤，再用一个问题确认。",
        mode: "progressive_explain",
        cardIndex: appState.activeCard,
        request: userRequest,
      },
      {
        label: "直接详细解释",
        description: "直接讲定义、作用、类比和边界。",
        mode: "direct_explain",
        cardIndex: appState.activeCard,
        request: userRequest,
      },
    ],
  });
}

function isRecordingDemoUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("demo") === "1" || params.get("recording") === "1";
}

async function loadRecordingDemoData() {
  try {
    const response = await fetch(DEMO_API_URL);
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  } catch (_error) {
    return { ok: true, mode: "recording_demo", ...recordingDemoFallback };
  }
}

function resetRecordingDemoState(data) {
  appState.demoMode = true;
  appState.demoData = data;
  appState.sources = [];
  appState.learningStyle = "苏格拉底";
  resetLearningResult();
  resetChat();
  addTextSource(data.fileName || recordingDemoFallback.fileName, data.material || recordingDemoFallback.material, "md");
  appState.learningGoal = data.goal || recordingDemoFallback.goal;
  appState.runtime = "录屏演示模式";
  appState.step = 1;
  answerInput.value = data.suggestedQuestion || recordingDemoFallback.suggestedQuestion;
  addMessage(
    "ai",
    "演示环境已准备好：固定资料、固定卡片、本地离线响应。录屏时点击下面按钮即可开始，不依赖网络和模型速度。",
    "录屏演示",
    {
      actions: [
        {
          action: "start-demo",
          label: "开始演示学习",
          description: "生成 3 张固定卡片并进入问答。",
          request: appState.learningGoal,
        },
      ],
    }
  );
}

async function seedRecordingDemo() {
  const data = await loadRecordingDemoData();
  resetRecordingDemoState(data);
  renderAll();
}

async function startRecordingDemoFlow(messageId, actionIndex) {
  const message = appState.chatMessages.find((item) => item.id === messageId);
  const action = message?.actions?.[actionIndex];
  if (!message || !action || message.resolved || appState.isThinking || appState.isAnalyzing) return;
  message.resolved = true;
  action.selected = true;
  addMessage("user", action.label, "你的选择");
  renderAll();
  await analyzeActiveSources(action.request || appState.learningGoal);
}

async function openKnowledgeCard(index, appendMessage = true, teachOptions = {}) {
  const card = appState.cards[index];
  if (!card) return;
  appState.activeCard = index;
  appState.step = 3;
  const isProgressiveExplain = teachOptions.supportMode === "progressive_explain";
  if (appendMessage) {
    addMessage("system", `切换到知识卡片 ${index + 1}：${card.title}`, "学习导航");
  }
  appState.runtime = isProgressiveExplain ? "渐进讲解" : "生成讲解";
  appState.isThinking = true;
  renderAll();

  try {
    const data = await postJson(TEACH_API_URL, cardPayload(card, teachOptions));
    if (teachOptions.supportMode === "direct_explain") {
      data.askFollowUp = false;
    }
    applyCardApiState(card, data);
    appState.runtime = data.source === "teacher_skill_llm" ? "真实讲解" : "本地讲解";
    addMessage("ai", data.content || `我先讲这一点：${card.answer}`, isProgressiveExplain ? "渐进讲解" : "讲解");
    if (data.askFollowUp !== false && (data.question || card.question)) {
      addMessage("ai", data.question || card.question, isProgressiveExplain ? "理解确认" : "验证问题");
    }
  } catch (error) {
    appState.runtime = "浏览器 fallback";
    addMessage("warning", `讲解 API 暂时不可用：${error.message}`, "降级处理");
    addMessage("ai", `我先讲这一点：${card.answer}`, "讲解");
    addMessage("ai", card.question, isProgressiveExplain ? "理解确认" : "验证问题");
  } finally {
    appState.isThinking = false;
    renderAll();
  }
}

async function requestProgressiveExplanation(card, userRequest) {
  const teachOptions = progressiveTeachOptionsFromRequest(userRequest);
  appState.step = 3;
  answerInput.value = "";
  appState.runtime = "渐进讲解";
  appState.isThinking = true;
  renderAll();

  try {
    const data = await postJson(TEACH_API_URL, cardPayload(card, teachOptions));
    if (teachOptions.supportMode === "direct_explain") {
      data.askFollowUp = false;
    }
    applyCardApiState(card, data);
    appState.runtime = data.source === "teacher_skill_llm" ? "真实讲解" : "本地讲解";
    card.status = "学习中";
    addMessage("ai", data.content || `我们换一种方式讲“${card.title}”：${card.answer}`, "渐进讲解");
    if (data.question || card.question) {
      addMessage("ai", data.question || card.question, "理解确认");
    }
  } catch (error) {
    appState.runtime = "浏览器 fallback";
    card.status = "学习中";
    addMessage(
      "warning",
      `讲解 API 暂时不可用：${error.message}。我先用本地方式讲：${card.answer}`,
      "降级讲解"
    );
  } finally {
    appState.isThinking = false;
    renderAll();
  }
}

function applyJudgeResult(card, data) {
  if (data.isCorrect) {
    appState.mastered.add(appState.activeCard);
    appState.review.delete(appState.activeCard);
    card.status = "已掌握";
    addMessage("feedback", data.content || "答对了，你已经抓住了核心。", "判卷反馈");
    return;
  }

  appState.mastered.delete(appState.activeCard);
  if (data.status === "needs_review" || data.action === "next_chunk") {
    appState.review.add(appState.activeCard);
    card.status = "待巩固";
  } else {
    card.status = "学习中";
  }
  addMessage("warning", data.content || "这次还不够完整，我给你一个提示后再试一次。", "渐进提示");
}

function applyExplainResult(card, data) {
  appState.mastered.delete(appState.activeCard);
  card.status = "学习中";
  const meta = data.askFollowUp === false ? "直接讲解" : "渐进讲解";
  addMessage("ai", data.content || `我们换一种方式讲“${card.title}”：${card.answer}`, meta);
  if (data.askFollowUp !== false && (data.question || card.question)) {
    addMessage("ai", data.question || card.question, "理解确认");
  }
}

function applyDirectAnswerResult(card, data) {
  appState.review.add(appState.activeCard);
  appState.mastered.delete(appState.activeCard);
  card.status = "待巩固";
  addMessage("warning", data.content || `参考答案：${card.answer}。这张卡片会先进入待巩固。`, "速查");
}

async function chooseExplainMode(messageId, actionIndex) {
  const message = appState.chatMessages.find((item) => item.id === messageId);
  const action = message?.actions?.[actionIndex];
  if (!message || !action || message.resolved || appState.isThinking || appState.isAnalyzing) return;

  message.resolved = true;
  action.selected = true;
  const card = appState.cards[action.cardIndex];
  if (!card) return;

  appState.activeCard = action.cardIndex;
  appState.step = 3;
  appState.runtime = action.mode === "direct_explain" ? "直接讲解" : "渐进讲解";
  appState.isThinking = true;
  addMessage("user", action.label, "你的选择");
  renderAll();

  try {
    const data = await postJson(
      TEACH_API_URL,
      cardPayload(card, {
        userRequest: action.request,
        supportMode: action.mode,
      })
    );
    if (action.mode === "direct_explain") {
      data.askFollowUp = false;
    }
    applyCardApiState(card, data);
    appState.runtime = data.source === "teacher_skill_llm" ? "真实讲解" : "本地讲解";
    applyExplainResult(card, data);
  } catch (error) {
    appState.runtime = "浏览器 fallback";
    const directMode = action.mode === "direct_explain";
    applyExplainResult(card, {
      content: directMode
        ? `我先直接讲“${card.title}”：${card.answer}`
        : `我先一步步讲“${card.title}”：${card.answer}`,
      question: directMode ? null : `轻量确认：现在你能不能用一句话说出“${card.title}”是什么？`,
      askFollowUp: !directMode,
    });
    addMessage("warning", `讲解 API 暂时不可用：${error.message}`, "降级处理");
  } finally {
    appState.isThinking = false;
    renderAll();
  }
}

function renderReport() {
  masteredMetric.textContent = appState.mastered.size;
  reviewMetric.textContent = appState.review.size;
  const rate = completionRate();
  rateMetric.textContent = `${rate}%`;

  reportTimeline.innerHTML = "";
  if (appState.cards.length === 0) {
    reportTimeline.innerHTML = `
      <div class="source-empty">
        问答开始后，这里会记录已掌握、待巩固和复习状态。
      </div>
    `;
    return;
  }

  appState.cards.forEach((card, index) => {
    const status = currentCardStatus(index, card);
    const item = document.createElement("div");
    item.className = "timeline-item";
    item.innerHTML = `
      <span class="timeline-dot ${appState.mastered.has(index) ? "mastered" : appState.review.has(index) ? "review" : ""}"></span>
      <strong>${escapeHtml(card.title)}</strong>
      <span>${escapeHtml(status)}</span>
    `;
    reportTimeline.appendChild(item);
  });
}

function renderProgress() {
  const rate = completionRate();
  currentStageLabel.textContent = stageTitle();
  progressText.textContent = `${rate}%`;
  progressBar.style.width = `${rate}%`;
  currentCardLabel.textContent = appState.cards.length
    ? `${appState.activeCard + 1}/${appState.cards.length}`
    : "-";
  sourceUsedLabel.textContent = String(activeSources().length);
  learningGoalLabel.textContent = appState.learningGoal || "等待你说明想学什么";
  nextActionLabel.textContent = nextActionText();
}

function renderStyles() {
  styleOptions.forEach((option) => {
    option.classList.toggle("is-active", option.dataset.style === appState.learningStyle);
  });
}

function renderAll() {
  renderSources();
  renderStages();
  renderStyles();
  renderCards();
  renderDialogue();
  renderReport();
  renderProgress();
  runtimeStatus.textContent = appState.runtime;
  if (demoResetButton) {
    demoResetButton.hidden = !appState.demoMode;
  }
  submitAnswer.disabled = appState.isAnalyzing || appState.isThinking;
  answerInput.disabled = appState.isAnalyzing || appState.isThinking;
  submitAnswer.textContent = appState.cards.length
    ? "提交"
    : activeSources().length > 0
      ? "开始学习"
      : "发送";
  directAnswer.disabled = appState.cards.length === 0 || appState.isAnalyzing || appState.isThinking;
  answerInput.placeholder = appState.cards.length
    ? "输入你的回答..."
    : activeSources().length > 0
      ? "说说你想学什么，例如：帮我理解这份资料的核心概念"
      : "上传文件，或直接粘贴一段材料并发送...";
}

async function analyzeActiveSources(goal = "") {
  const sources = activeSources();
  if (sources.length === 0 || appState.isAnalyzing) return;

  if (appState.demoMode) {
    appState.learningGoal = goal.trim() || appState.learningGoal || recordingDemoFallback.goal;
    appState.isAnalyzing = true;
    appState.runtime = "演示分析中";
    appState.step = 2;
    appState.isThinking = true;
    addMessage("system", "录屏演示会使用固定离线卡片，保证每次展示结果一致。", "演示保障");
    renderAll();
    await delay(250);
    appState.cards = cardsFromDemoData(appState.demoData || recordingDemoFallback);
    appState.activeCard = 0;
    appState.mastered.clear();
    appState.review.clear();
    appState.runtime = "演示卡片已生成";
    appState.step = 3;
    appState.isAnalyzing = false;
    appState.isThinking = false;
    addMessage("feedback", `已生成 ${appState.cards.length} 张演示知识卡片。`, "卡片生成");
    await openKnowledgeCard(0, false, {});
    renderAll();
    return;
  }

  const pdfSources = sources.filter((source) => source.kind === "pdf");
  if (pdfSources.length > 0 && sources.length > 1) {
    appState.runtime = "PDF 请单独学习";
    appState.step = 1;
    addMessage("warning", "当前版本建议 PDF 单独学习。请只勾选一个 PDF，或先取消 PDF 后学习 txt/md。", "资料检查");
    renderAll();
    return;
  }

  appState.learningGoal = goal.trim() || appState.learningGoal || "先帮我建立整体理解";
  appState.isAnalyzing = true;
  appState.runtime = "分析中";
  appState.step = 2;
  appState.isThinking = true;
  addMessage("system", `已选择 ${sources.length} 份资料作为学习来源。`, "资料接收");
  const initialTeachOptions = progressiveTeachOptionsFromRequest(appState.learningGoal);
  addMessage(
    "ai",
    initialTeachOptions.supportMode === "progressive_explain"
      ? `我会按你的请求直接进入渐进讲解：先把概念讲清楚，再给一个轻量理解确认。`
      : `我会围绕“${appState.learningGoal}”，用“${appState.learningStyle}”风格拆解资料：先讲清楚，再用问题验证你是否真的理解。`,
    "学习流程"
  );
  renderAll();
  await delay(350);
  addMessage("system", "正在提取关键概念、定义、例子和容易混淆的边界。", "分析中");
  renderAll();

  const singlePdf = pdfSources[0];
  const sourceMaterial = singlePdf ? singlePdf.name : combinedTextFromSources(activeTextSources());
  const material = singlePdf
    ? sourceMaterial
    : `# 学习目标\n\n${appState.learningGoal}\n\n# 学习材料\n\n${sourceMaterial}`;

  try {
    const payload = singlePdf
      ? {
          text: "",
          fileName: singlePdf.name,
          fileDataBase64: singlePdf.dataBase64,
          mimeType: singlePdf.mimeType,
          userLevel: "beginner",
          useRealEngine: true,
        }
      : {
          text: material,
          fileName: sources.length === 1 ? sources[0].name : "combined-sources.md",
          fileDataBase64: "",
          mimeType: "text/markdown",
          userLevel: "beginner",
          useRealEngine: true,
        };

    const data = await postJson(ANALYZE_API_URL, payload);

    const cards = cardsFromApiResult(data);
    appState.cards = cards.length > 0 ? cards : localCardsFromMaterial(data.extractedText || material);
    appState.activeCard = 0;
    appState.mastered.clear();
    appState.review.clear();
    appState.runtime = data.source === "teacher_skill_llm" ? "真实引擎" : "本地 fallback";
    appState.step = 3;
    appState.isThinking = false;
    addMessage("feedback", `已生成 ${appState.cards.length} 张知识卡片。`, "卡片生成");
    await openKnowledgeCard(0, false, initialTeachOptions);
  } catch (error) {
    appState.cards = localCardsFromMaterial(material || demoMaterial);
    appState.activeCard = 0;
    appState.mastered.clear();
    appState.review.clear();
    appState.runtime = "浏览器 fallback";
    appState.step = 3;
    appState.isThinking = false;
    addMessage("warning", `本地 API 暂时不可用，已用浏览器 fallback 生成 ${appState.cards.length} 张知识卡片。`, "降级处理");
    await openKnowledgeCard(0, false, initialTeachOptions);
  } finally {
    appState.isAnalyzing = false;
    appState.isThinking = false;
    renderAll();
  }
}

async function handleUpload(event) {
  const files = [...(event.target.files || [])];
  if (files.length === 0) return;
  clearStaleCardsAfterSourceChange();
  for (const file of files) {
    await addFileSource(file);
  }
  event.target.value = "";
  setWaitingForGoal();
  addMessage(
    "system",
    `已添加 ${files.length} 个文件。现在还没有开始分析，请在中间告诉我这次想学什么。`,
    "等待目标"
  );
  renderAll();
}

async function handleSend() {
  const value = answerInput.value.trim();
  if (!value) return;

  if (appState.cards.length === 0) {
    answerInput.value = "";
    if (activeSources().length > 0 && !looksLikeMaterial(value)) {
      addMessage("user", value, "学习目标");
      renderAll();
      await analyzeActiveSources(value);
      return;
    }

    if (looksLikeMaterial(value)) {
      addMessage("user", value, "粘贴资料");
      addTextSource(`聊天粘贴资料 ${appState.sources.length + 1}`, value, "txt");
      appState.learningGoal = "先帮我建立整体理解";
      addMessage("system", "我已把这段内容保存为资料，并按“整体理解”开始拆解。", "资料接收");
      renderAll();
      await analyzeActiveSources(appState.learningGoal);
      return;
    }

    addMessage("user", value, "学习目标");
    addMessage("warning", "我还没有可用资料。请先上传 txt/md/pdf，或直接粘贴一段较完整的学习材料。", "缺少资料");
    appState.runtime = "等待资料";
    appState.step = 0;
    renderAll();
    return;
  }

  const card = appState.cards[appState.activeCard];
  addMessage("user", value, "你的输入");
  appState.step = 3;
  answerInput.value = "";
  if (classifyLearningInput(value, card) === "explain") {
    addExplainModeChoice(card, value);
    renderAll();
    return;
  }

  appState.runtime = "AI 判断中";
  appState.isThinking = true;
  renderAll();

  try {
    const data = await postJson(RESPOND_API_URL, cardPayload(card, { userInput: value, answer: value }));
    applyCardApiState(card, data);

    if (data.intent === "explain") {
      appState.runtime = data.source === "teacher_skill_llm" ? "真实讲解" : "本地讲解";
      applyExplainResult(card, data);
    } else if (data.intent === "direct_answer") {
      appState.runtime = data.source === "teacher_skill_llm" ? "真实速查" : "本地速查";
      applyDirectAnswerResult(card, data);
    } else {
      appState.runtime = data.source === "teacher_skill_llm" ? "真实判卷" : "本地判卷";
      applyJudgeResult(card, data);
    }
  } catch (error) {
    const localIntent = classifyLearningInput(value, card);
    try {
      if (localIntent === "explain") {
        const teachOptions = progressiveTeachOptionsFromRequest(value);
        const data = await postJson(TEACH_API_URL, cardPayload(card, teachOptions));
        if (teachOptions.supportMode === "direct_explain") {
          data.askFollowUp = false;
        }
        applyCardApiState(card, data);
        appState.runtime = data.source === "teacher_skill_llm" ? "真实讲解" : "本地讲解";
        applyExplainResult(card, data);
        return;
      }

      if (localIntent === "direct_answer") {
        const data = await postJson(
          HINT_API_URL,
          cardPayload(card, {
            direct: true,
            hintLevel: card.hintLevel || 0,
            userRequest: value,
          })
        );
        applyCardApiState(card, data);
        appState.runtime = data.source === "teacher_skill_llm" ? "真实速查" : "本地速查";
        applyDirectAnswerResult(card, data);
        return;
      }

      const data = await postJson(JUDGE_API_URL, cardPayload(card, { answer: value }));
      applyCardApiState(card, data);
      appState.runtime = data.source === "teacher_skill_llm" ? "真实判卷" : "本地判卷";
      applyJudgeResult(card, data);
      return;
    } catch (legacyError) {
      appState.runtime = "浏览器 fallback";
      if (localIntent === "explain") {
        applyExplainResult(card, {
          content: `我先按本地方式渐进讲解“${card.title}”：${card.answer}`,
          question: `轻量确认：现在你能不能用一句话说出“${card.title}”是什么？`,
          askFollowUp: !/不太能|不太会|答不上来|直接讲|直接说|直接跟我说|直接告诉我|跟我说这个概念|说这个概念|告诉我这个概念|可以直接/.test(value),
        });
        addMessage("warning", `统一响应 API 暂时不可用：${error.message}；旧接口也不可用：${legacyError.message}`, "降级处理");
      } else if (localIntent === "direct_answer") {
        applyDirectAnswerResult(card, {
          content: `参考答案：${card.answer}。这张卡片会先进入待巩固。`,
        });
        addMessage("warning", `统一响应 API 暂时不可用：${error.message}；旧接口也不可用：${legacyError.message}`, "降级处理");
      } else {
        card.failCount = (card.failCount || 0) + 1;
        card.hintLevel = Math.min((card.hintLevel || 0) + 1, 4);
        card.status = "学习中";
        addMessage("warning", `统一响应 API 暂时不可用：${error.message}；旧判卷接口也不可用：${legacyError.message}。先给你一个本地提示：请围绕“${card.title}”的定义、作用和边界再答一次。`, "降级处理");
      }
    }
  } finally {
    appState.isThinking = false;
    renderAll();
  }
}

async function revealCurrentAnswer(userRequest = "速查答案") {
  if (appState.cards.length === 0) return;
  const card = appState.cards[appState.activeCard];
  if (userRequest === "速查答案") {
    addMessage("user", userRequest, "你的选择");
  }
  appState.step = 3;
  appState.runtime = "生成提示";
  appState.isThinking = true;
  renderAll();

  try {
    const data = await postJson(
      HINT_API_URL,
      cardPayload(card, {
        direct: true,
        hintLevel: card.hintLevel || 0,
        userRequest,
      })
    );
    applyCardApiState(card, data);
    appState.runtime = data.source === "teacher_skill_llm" ? "真实速查" : "本地速查";
    appState.review.add(appState.activeCard);
    appState.mastered.delete(appState.activeCard);
    card.status = "待巩固";
    addMessage("warning", data.content || `参考答案：${card.answer}。这张卡片会先进入待巩固。`, "速查");
  } catch (error) {
    appState.runtime = "浏览器 fallback";
    appState.review.add(appState.activeCard);
    appState.mastered.delete(appState.activeCard);
    card.status = "待巩固";
    addMessage("warning", `速查 API 暂时不可用：${error.message}。参考答案：${card.answer}`, "降级处理");
  } finally {
    appState.isThinking = false;
    renderAll();
  }
}

sourceUpload.addEventListener("change", handleUpload);
submitAnswer.addEventListener("click", handleSend);
directAnswer.addEventListener("click", () => revealCurrentAnswer());
dialogueBox.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-chat-action]");
  if (!button) return;
  if (button.dataset.chatAction === "start-demo") {
    startRecordingDemoFlow(button.dataset.messageId, Number(button.dataset.actionIndex));
    return;
  }
  if (button.dataset.chatAction === "explain-mode") {
    chooseExplainMode(button.dataset.messageId, Number(button.dataset.actionIndex));
  }
});
answerInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") handleSend();
});

sourceList.addEventListener("change", async (event) => {
  const target = event.target;
  if (!target.classList.contains("source-enable")) return;
  const source = appState.sources.find((item) => item.id === target.dataset.id);
  if (!source) return;
  source.enabled = target.checked;
  clearStaleCardsAfterSourceChange();
  setWaitingForGoal();
  appState.runtime = source.enabled ? "资料已启用，等待目标" : "资料已停用，等待目标";
  renderAll();
});

sourceList.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const source = appState.sources.find((item) => item.id === button.dataset.id);
  if (!source) return;

  if (button.dataset.action === "rename") {
    const nextName = window.prompt("重命名资料", source.name);
    if (nextName && nextName.trim()) {
      source.name = nextName.trim();
      appState.runtime = "资料已重命名";
    }
  }

  if (button.dataset.action === "delete") {
    const confirmed = window.confirm(`删除“${source.name}”？`);
    if (confirmed) {
      clearStaleCardsAfterSourceChange();
      appState.sources = appState.sources.filter((item) => item.id !== source.id);
      appState.runtime = "资料已删除";
      if (appState.sources.length === 0) {
        resetLearningResult();
        resetChat();
        appState.learningGoal = "";
        appState.step = 0;
      } else {
        setWaitingForGoal();
      }
    }
  }

  renderAll();
});

styleOptions.forEach((option) => {
  option.addEventListener("click", () => {
    appState.learningStyle = option.dataset.style;
    addMessage("system", `学习风格已切换为：${appState.learningStyle}`, "学习设置");
    renderAll();
  });
});

if (demoResetButton) {
  demoResetButton.addEventListener("click", () => {
    seedRecordingDemo();
  });
}

if (isRecordingDemoUrl()) {
  seedRecordingDemo();
} else {
  renderAll();
}
