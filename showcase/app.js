const demoState = {
  step: 0,
  activeCard: 0,
  mastered: new Set(),
  review: new Set(),
  cards: [
    {
      title: "自注意力",
      difficulty: "medium",
      question: "自注意力主要解决什么问题？",
      answer: "计算 token 之间的关系权重",
      status: "学习中",
    },
    {
      title: "位置编码",
      difficulty: "easy",
      question: "为什么 Transformer 需要位置编码？",
      answer: "因为没有 RNN 那样的天然顺序结构",
      status: "未开始",
    },
    {
      title: "多头注意力",
      difficulty: "medium",
      question: "多头注意力的价值是什么？",
      answer: "并行捕捉不同特征",
      status: "未开始",
    },
  ],
};

const materialInput = document.querySelector("#materialInput");
const charCount = document.querySelector("#charCount");
const knowledgeList = document.querySelector("#knowledgeList");
const dialogueBox = document.querySelector("#dialogueBox");
const answerInput = document.querySelector("#answerInput");
const submitAnswer = document.querySelector("#submitAnswer");
const directAnswer = document.querySelector("#directAnswer");
const analyzeButton = document.querySelector("#analyzeButton");
const masteredMetric = document.querySelector("#masteredMetric");
const reviewMetric = document.querySelector("#reviewMetric");
const rateMetric = document.querySelector("#rateMetric");
const reportTimeline = document.querySelector("#reportTimeline");
const nextStep = document.querySelector("#nextStep");
const prevStep = document.querySelector("#prevStep");
const stepItems = [...document.querySelectorAll(".step-item")];

function updateCharCount() {
  charCount.textContent = `${materialInput.value.trim().length} 字符`;
}

function renderCards() {
  knowledgeList.innerHTML = "";
  demoState.cards.forEach((card, index) => {
    const item = document.createElement("button");
    item.className = `knowledge-card${index === demoState.activeCard ? " is-active" : ""}`;
    item.type = "button";
    item.innerHTML = `
      <div class="card-title-row">
        <strong>${index + 1}. ${card.title}</strong>
        <span>${card.difficulty}</span>
      </div>
      <p>${card.question}</p>
      <div class="card-status">${card.status}</div>
    `;
    item.addEventListener("click", () => {
      demoState.activeCard = index;
      demoState.step = Math.max(demoState.step, 2);
      renderAll();
    });
    knowledgeList.appendChild(item);
  });
}

function bubble(text, type = "ai") {
  const item = document.createElement("div");
  item.className = `bubble ${type}`;
  item.textContent = text;
  dialogueBox.appendChild(item);
}

function renderDialogue() {
  const card = demoState.cards[demoState.activeCard];
  dialogueBox.innerHTML = "";
  bubble(`讲解：${card.title} 是这个材料里的关键知识点。`, "ai");
  bubble(`验证问题：${card.question}`, "ai");

  if (demoState.mastered.has(demoState.activeCard)) {
    bubble(answerInput.value || card.answer, "user");
    bubble(`判卷通过：你抓住了核心，${card.answer}。`, "feedback");
  }

  if (demoState.review.has(demoState.activeCard)) {
    bubble("用户选择速查", "user");
    bubble(`速查答案：${card.answer}。系统已标记为待巩固。`, "warning");
  }
}

function renderReport() {
  masteredMetric.textContent = demoState.mastered.size;
  reviewMetric.textContent = demoState.review.size;
  const done = demoState.mastered.size + demoState.review.size;
  rateMetric.textContent = `${Math.round((done / demoState.cards.length) * 100)}%`;

  reportTimeline.innerHTML = "";
  demoState.cards.forEach((card, index) => {
    const status = demoState.mastered.has(index)
      ? "已掌握"
      : demoState.review.has(index)
        ? "待巩固"
        : card.status;
    const item = document.createElement("div");
    item.className = "timeline-item";
    item.innerHTML = `
      <span class="timeline-dot ${demoState.mastered.has(index) ? "mastered" : demoState.review.has(index) ? "review" : ""}"></span>
      <strong>${card.title}</strong>
      <span>${status}</span>
    `;
    reportTimeline.appendChild(item);
  });
}

function renderSteps() {
  stepItems.forEach((item, index) => {
    item.classList.toggle("is-active", index === demoState.step);
  });
  nextStep.textContent = demoState.step >= 3 ? "完成演示" : "下一步";
}

function renderAll() {
  updateCharCount();
  renderCards();
  renderDialogue();
  renderReport();
  renderSteps();
}

function moveStep(delta) {
  demoState.step = Math.max(0, Math.min(3, demoState.step + delta));
  if (demoState.step === 1) {
    demoState.cards.forEach((card, index) => {
      card.status = index === 0 ? "学习中" : "未开始";
    });
  }
  if (demoState.step >= 2) {
    demoState.activeCard = Math.min(demoState.activeCard, demoState.cards.length - 1);
  }
  renderAll();
}

materialInput.addEventListener("input", updateCharCount);

analyzeButton.addEventListener("click", () => {
  demoState.step = 1;
  renderAll();
});

submitAnswer.addEventListener("click", () => {
  demoState.mastered.add(demoState.activeCard);
  demoState.review.delete(demoState.activeCard);
  demoState.cards[demoState.activeCard].status = "已掌握";
  demoState.step = Math.max(demoState.step, 3);
  renderAll();
});

directAnswer.addEventListener("click", () => {
  demoState.review.add(demoState.activeCard);
  demoState.mastered.delete(demoState.activeCard);
  demoState.cards[demoState.activeCard].status = "待巩固";
  demoState.step = Math.max(demoState.step, 3);
  renderAll();
});

nextStep.addEventListener("click", () => moveStep(1));
prevStep.addEventListener("click", () => moveStep(-1));

stepItems.forEach((item) => {
  item.addEventListener("click", () => {
    demoState.step = Number(item.dataset.step);
    renderAll();
  });
});

renderAll();
