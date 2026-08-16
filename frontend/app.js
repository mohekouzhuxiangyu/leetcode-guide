/* 力扣算法学习助手 · 前端逻辑 */
"use strict";

const $ = (id) => document.getElementById(id);
const STAGES = ["fetch", "translate", "analyze", "walkthrough", "flowchart", "code", "done"];
const DIFF_ZH = { Easy: "简单", Medium: "中等", Hard: "困难", Unknown: "未知" };
const LANG_ALIAS = {
  Python3: { label: "🐍 Python3", hl: "python" },
  Java: { label: "☕ Java", hl: "java" },
  "C++": { label: "⚙️ C++", hl: "cpp" },
};

let currentJobId = null;
let currentSlug = null;
let pollTimer = null;
let mermaidSeq = 0;

/* 会话状态：记录缓存 + 标签页懒渲染 + 分类筛选 + 批量生成 */
const state = {
  record: null,
  renderedTabs: {},
  cache: {},
  categoryFilter: "全部",
  historyItems: [],
  templates: null,
  hot100: null,
  batchTimer: null,
};

/* ---------- 工具函数 ---------- */

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      return true;
    } catch {
      return false;
    }
  }
}

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function highlightAll(container) {
  if (typeof hljs === "undefined") return;
  container.querySelectorAll("pre code").forEach((c) => {
    try { hljs.highlightElement(c); } catch (e) { /* ignore */ }
  });
}

function renderMarkdown(text) {
  if (typeof marked !== "undefined") {
    try { return marked.parse(text); } catch (e) { /* ignore */ }
  }
  return `<pre style="white-space:pre-wrap;word-break:break-word;">${escapeHtml(text)}</pre>`;
}

/* ---------- Mermaid 消毒 ---------- */

function quoteMermaidText(text) {
  text = text.trim();
  if (text.length >= 2 && text.startsWith('"') && text.endsWith('"')) return text;
  return '"' + text.replace(/"/g, "#quot;") + '"';
}

function findMatching(s, start, openCh, closeCh) {
  let depth = 0;
  for (let idx = start; idx < s.length; idx++) {
    if (s[idx] === openCh) depth++;
    else if (s[idx] === closeCh) {
      depth--;
      if (depth === 0) return idx;
    }
  }
  return -1;
}

function quoteNodeTexts(line) {
  let out = "";
  let i = 0;
  const n = line.length;
  while (i < n) {
    const ch = line[i];
    if (/[A-Za-z0-9_]/.test(ch)) {
      let j = i;
      while (j < n && /[A-Za-z0-9_]/.test(line[j])) j++;
      const ident = line.slice(i, j);
      let k = j;
      while (k < n && line[k] === " ") k++;
      if (k < n && "[{(>".includes(line[k])) {
        const shape = line[k];
        if (shape === "(") {
          if (k + 1 < n && line[k + 1] === "(") {
            const close = findMatching(line, k + 1, "(", ")");
            if (close !== -1 && close + 1 < n && line[close + 1] === ")") {
              out += ident + "((" + quoteMermaidText(line.slice(k + 2, close)) + "))";
              i = close + 2;
              continue;
            }
          } else if (k + 1 < n && line[k + 1] === "[") {
            const close = findMatching(line, k + 1, "[", "]");
            if (close !== -1 && close + 1 < n && line[close + 1] === ")") {
              out += ident + "([" + quoteMermaidText(line.slice(k + 2, close)) + "])";
              i = close + 2;
              continue;
            }
          } else {
            const close = findMatching(line, k, "(", ")");
            if (close !== -1) {
              out += ident + "(" + quoteMermaidText(line.slice(k + 1, close)) + ")";
              i = close + 1;
              continue;
            }
          }
        } else if (shape === "[") {
          const close = findMatching(line, k, "[", "]");
          if (close !== -1) {
            out += ident + "[" + quoteMermaidText(line.slice(k + 1, close)) + "]";
            i = close + 1;
            continue;
          }
        } else if (shape === "{") {
          const close = findMatching(line, k, "{", "}");
          if (close !== -1) {
            out += ident + "{" + quoteMermaidText(line.slice(k + 1, close)) + "}";
            i = close + 1;
            continue;
          }
        } else if (shape === ">") {
          const close = findMatching(line, k, ">", "]");
          if (close !== -1) {
            out += ident + ">" + quoteMermaidText(line.slice(k + 1, close)) + "]";
            i = close + 1;
            continue;
          }
        }
      }
      out += ident;
      i = j;
    } else {
      out += ch;
      i++;
    }
  }
  return out;
}

function sanitizeMermaid(code) {
  const lines = String(code || "").split("\n");
  const out = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || /^(flowchart|graph|subgraph|end|style|classDef|class |%%|direction)\b/.test(line)) {
      out.push(raw);
      continue;
    }
    out.push(quoteNodeTexts(line));
  }
  return out.join("\n");
}

async function renderMermaidGraph(container, code) {
  if (typeof mermaid === "undefined") {
    container.innerHTML = `<div class="mermaid-error">流程图渲染库未加载，以下是 Mermaid 源码：</div><pre style="text-align:left;white-space:pre-wrap;">${escapeHtml(code)}</pre>`;
    return;
  }
  mermaidSeq += 1;
  const id = "mermaid-graph-" + mermaidSeq + "-" + Date.now();
  try {
    const { svg } = await mermaid.render(id, code);
    container.innerHTML = svg;
    container.querySelector("svg").style.maxWidth = "100%";
  } catch (err) {
    container.innerHTML = `<div class="mermaid-error">流程图渲染失败：${escapeHtml(err.message)}<br/>可点击下方“查看 Mermaid 源码”复制内容。</div>`;
  }
}

/* ---------- 页面状态切换 ---------- */

function showInputOnly() {
  hide($("progress-panel"));
  hide($("result-panel"));
  hide($("error-panel"));
  hide($("templates-panel"));
  show($("input-panel"));
}

function showProgress() {
  hide($("input-panel"));
  hide($("result-panel"));
  hide($("error-panel"));
  hide($("templates-panel"));
  show($("progress-panel"));
  $("progress-steps").querySelectorAll("li").forEach((li) => {
    li.classList.remove("active", "done");
  });
  $("progress-msg").textContent = "";
}

function showResult() {
  hide($("input-panel"));
  hide($("progress-panel"));
  hide($("error-panel"));
  hide($("templates-panel"));
  show($("result-panel"));
}

function showError(msg) {
  hide($("input-panel"));
  hide($("progress-panel"));
  hide($("result-panel"));
  hide($("templates-panel"));
  const el = $("error-panel");
  el.textContent = msg;
  show(el);
}

/* ---------- 生成流程 ---------- */

async function submitGenerate(url) {
  currentJobId = null;
  showProgress();
  try {
    const resp = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "请求失败");
    currentJobId = data.job_id;
    pollTimer = setInterval(pollJob, 1500);
    pollJob();
  } catch (err) {
    showError("提交失败：" + err.message);
  }
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const resp = await fetch("/api/jobs/" + currentJobId);
    const job = await resp.json();
    if (!resp.ok) throw new Error(job.detail || "查询任务失败");

    const stageIdx = STAGES.indexOf(job.stage);
    $("progress-steps").querySelectorAll("li").forEach((li) => {
      li.classList.remove("active", "done");
      const sIdx = STAGES.indexOf(li.dataset.stage);
      if (job.status === "running" && sIdx < stageIdx) li.classList.add("done");
      if (sIdx === stageIdx) li.classList.add("active");
    });
    if (job.status === "done") {
      STAGES.forEach((s) => {
        const li = $("progress-steps").querySelector(`li[data-stage="${s}"]`);
        if (li) li.classList.add("done");
      });
    }
    $("progress-msg").textContent = job.message || "";

    if (job.status === "done") {
      clearInterval(pollTimer);
      pollTimer = null;
      currentJobId = null;
      try {
        renderResult(job.result);
        showResult();
        loadHistory();
      } catch (err) {
        console.error("渲染结果失败:", err);
        showError("渲染结果失败：" + err.message);
      }
    } else if (job.status === "error") {
      clearInterval(pollTimer);
      pollTimer = null;
      currentJobId = null;
      showError("生成失败：" + (job.error || "未知错误"));
    }
  } catch (err) {
    clearInterval(pollTimer);
    pollTimer = null;
    currentJobId = null;
    showError("查询任务失败：" + err.message);
  }
}

/* ---------- 题目信息分节解析 ---------- */

function parseProblemSections(text) {
  const lines = text.split("\n");
  const description = [];
  const examples = [];
  const constraints = [];
  let mode = "desc";
  let cur = null;
  for (const ln of lines) {
    const t = ln.trim();
    const exM = t.match(/^(示例|Example)\s*(\d*)\s*[:：]?\s*(.*)$/);
    const conM = t.match(/^(约束|提示|Constraints)\s*[:：]?(.*)$/);
    if (t !== "```" && exM) {
      if (exM[2] !== "" || exM[3].trim() !== "") {
        mode = "ex";
        cur = { title: t, body: [] };
        examples.push(cur);
      }
      continue;
    }
    if (t !== "```" && conM) {
      mode = "con";
      if (conM[2].trim() !== "") constraints.push(ln);
      continue;
    }
    if (mode === "desc") description.push(ln);
    else if (mode === "ex" && cur) cur.body.push(ln);
    else constraints.push(ln);
  }
  for (const ex of examples) {
    let b = ex.body.join("\n").trim();
    b = b.replace(/^```\w*\s*\n?/, "").replace(/\n?```$/, "");
    ex.body = b;
  }
  return {
    description: description.join("\n").trim(),
    examples,
    constraints: constraints.join("\n").trim(),
  };
}

/* ---------- 结果渲染（懒渲染 + 缓存） ---------- */

function renderResult(record) {
  currentSlug = record.slug;
  state.record = record;
  state.renderedTabs = {};
  state.cache[record.slug] = record;
  window.__codeMap = record.code || {};
  const problem = record.problem || {};

  $("result-title").textContent = `${record.title || problem.title_cn || problem.title || record.slug} #${problem.id || ""}`;
  const diff = $("result-difficulty");
  diff.textContent = DIFF_ZH[problem.difficulty] || problem.difficulty || "未知";
  diff.className = "badge " + (problem.difficulty || "Unknown");

  const catEl = $("result-category");
  if (record.category && record.category !== "其他") {
    catEl.textContent = "🗂 " + record.category;
    catEl.classList.remove("hidden");
  } else {
    catEl.classList.add("hidden");
  }

  const tagRow = $("result-tags");
  tagRow.innerHTML = "";
  (problem.tags || []).forEach((t) => {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = t;
    tagRow.appendChild(span);
  });

  const link = $("result-link");
  link.href = problem.url || record.url || "#";

  const note = (problem.source === "llm") ? "（题目原文由模型根据知识补全）" : "";
  const timeText = record.updated_at || record.created_at || new Date().toLocaleString();
  $("result-time").textContent = `生成于 ${timeText} ${note}`;

  // 固定题目描述（置顶，便于与下方内容对比）
  const ps = $("problem-sticky");
  const descRaw = (record.problem_zh || problem.content_text || "").trim();
  if (descRaw) {
    const { description } = parseProblemSections(descRaw);
    $("ps-body").textContent = description || descRaw;
    ps.classList.remove("hidden");
    ps.classList.add("open");
  } else {
    ps.classList.add("hidden");
  }

  renderProblemTab(problem, record);
  state.renderedTabs.problem = true;

  setActiveHistory(record.slug);
  switchTab("problem");
}

function renderProblemTab(problem, record) {
  const el = $("tab-problem");
  const content = (problem.content_text || "").trim();
  const snippets = problem.code_snippets || {};
  const zh = (record.problem_zh || "").trim();
  let html = "";
  if (zh || content) {
    const { description, examples, constraints } = parseProblemSections(zh || content);
    // 描述与约束支持 Markdown（反引号/加粗/列表正确渲染），示例保持代码块
    if (description) html += `<div class="problem-desc">${renderMarkdown(description)}</div>`;
    if (examples.length) {
      html += `<h3 class="sec-title">📌 示例</h3>`;
      for (const ex of examples) {
        html += `<div class="problem-example"><div class="example-title">${escapeHtml(ex.title)}</div>`;
        if (ex.body) html += `<pre>${escapeHtml(ex.body)}</pre>`;
        html += `</div>`;
      }
    }
    if (constraints) {
      html += `<h3 class="sec-title">⚠️ 约束</h3><div class="problem-constraints">${renderMarkdown(constraints)}</div>`;
    }
  } else {
    html += `<div class="problem-empty">（未获取到题目原文，请查看算法解析或<a href="${escapeHtml(problem.url || record.url || "#")}" target="_blank">原题链接</a>）</div>`;
  }
  if (Object.keys(snippets).length) {
    html += `<h3 class="sec-title">🧩 LeetCode 函数模板</h3>`;
    for (const [lang, code] of Object.entries(snippets)) {
      html += `<div class="code-block"><pre><code class="language-${LANG_ALIAS[lang]?.hl || "text"}">${escapeHtml(code)}</code></pre></div>`;
    }
  }
  el.innerHTML = html;
  highlightAll(el);
}

function renderAnalysisTab(analysis) {
  const el = $("tab-analysis");
  if (!analysis || !analysis.trim()) {
    el.innerHTML = `<p class="problem-empty">算法解析生成失败。</p>`;
    return;
  }
  el.innerHTML = renderMarkdown(analysis);
  highlightAll(el);
}

function renderFlowchartTab(mermaidCode) {
  const code = sanitizeMermaid(mermaidCode || "");
  $("mermaid-source-pre").textContent = code;
  const container = $("mermaid-container");
  if (!code.trim()) {
    container.innerHTML = `<div class="mermaid-error">流程图生成失败。</div>`;
    return;
  }
  container.innerHTML = `<div class="mermaid-loading">⏳ 流程图渲染中…</div>`;
  renderMermaidGraph(container, code);
}

function renderCodeTab(codeMap) {
  const langs = Object.keys(codeMap || {});
  const langBar = $("code-langs");
  const container = $("code-container");
  langBar.innerHTML = "";
  container.innerHTML = "";

  if (!langs.length) {
    container.innerHTML = `<p class="problem-empty">代码生成失败。</p>`;
    return;
  }

  langs.forEach((lang, i) => {
    const btn = document.createElement("button");
    btn.className = "code-lang-btn" + (i === 0 ? " active" : "");
    btn.textContent = LANG_ALIAS[lang]?.label || lang;
    btn.dataset.lang = lang;
    btn.addEventListener("click", () => showCodeLang(lang));
    langBar.appendChild(btn);
  });
  showCodeLang(langs[0]);
}

function showCodeLang(lang) {
  document.querySelectorAll(".code-lang-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.lang === lang);
  });
  const container = $("code-container");
  const allCodes = window.__codeMap || {};
  const code = allCodes[lang] || "";
  const alias = LANG_ALIAS[lang] || { label: lang, hl: "text" };
  container.innerHTML = `
    <div class="code-block">
      <button class="code-copy" data-copy>📋 复制</button>
      <pre><code class="language-${alias.hl}">${escapeHtml(code)}</code></pre>
    </div>`;
  highlightAll(container);
  container.querySelector("[data-copy]").addEventListener("click", async (e) => {
    const ok = await copyText(code);
    e.target.textContent = ok ? "✅ 已复制" : "❌ 复制失败";
    setTimeout(() => { e.target.textContent = "📋 复制"; }, 1500);
  });
}

/* ---------- 动画演示（逐步播放，带真实动画） ---------- */

const wt = { steps: [], idx: 0, timer: null, arrayLen: 0, prevData: null, extraKey: "" };

function renderWalkthroughTab(raw) {
  const container = $("walkthrough-container");
  let steps = [];
  try { steps = JSON.parse(raw || "[]"); } catch (e) { steps = []; }
  if (!Array.isArray(steps) || !steps.length) {
    container.innerHTML = `<div class="problem-empty">动画演示生成失败（可点击「重新生成」重试）。</div>`;
    return;
  }
  wt.steps = steps;
  wt.idx = 0;
  wt.timer = null;
  wt.arrayLen = 0;
  wt.prevData = null;
  wt.extraKey = "";
  // 预收集所有步骤中出现过的指针名，保证指针 DOM 一次建全
  wt.ptrNames = [];
  for (const s of steps) {
    const arr = (s.data || {}).array;
    if (Array.isArray(arr)) wt.arrayLen = Math.max(wt.arrayLen, arr.length);
    for (const name of Object.keys((s.data || {}).pointers || {})) {
      if (!wt.ptrNames.includes(name)) wt.ptrNames.push(name);
    }
  }
  container.innerHTML = `
    <div class="wt-tip">🎬 逐步动画：点击「下一步」观察指针滑动与格子变化，或自动播放</div>
    <div class="wt-board">
      <div class="wt-title" id="wt-title"></div>
      <div class="wt-visual" id="wt-visual"></div>
      <div class="wt-note" id="wt-note"></div>
    </div>
    <div class="wt-controls">
      <button class="btn btn-small" id="wt-prev">◀ 上一步</button>
      <span class="wt-counter" id="wt-counter"></span>
      <button class="btn btn-small" id="wt-next">下一步 ▶</button>
      <button class="btn btn-small" id="wt-play">▶ 自动播放</button>
    </div>
    <div class="wt-dots" id="wt-dots"></div>`;
  $("wt-prev").addEventListener("click", () => wtStep(-1));
  $("wt-next").addEventListener("click", () => wtStep(1));
  $("wt-play").addEventListener("click", wtTogglePlay);
  renderWtStep();
}

function renderWtStep() {
  const s = wt.steps[wt.idx] || {};
  const data = s.data || {};

  const title = $("wt-title");
  title.textContent = `第 ${wt.idx + 1} 步：${s.title || ""}`;

  renderWtVisual(data, wt.prevData);
  wt.prevData = data;

  // 说明文字淡入
  const note = $("wt-note");
  note.textContent = s.note || "";
  note.classList.remove("fade");
  void note.offsetWidth;
  note.classList.add("fade");

  // 计数器 / 进度点 / 按钮状态
  $("wt-counter").textContent = `${wt.idx + 1} / ${wt.steps.length}`;
  $("wt-dots").innerHTML = wt.steps
    .map((_, k) => `<span class="wt-dot${k === wt.idx ? " active" : ""}" data-k="${k}"></span>`)
    .join("");
  $("wt-dots").querySelectorAll(".wt-dot").forEach((d) => {
    d.addEventListener("click", () => { wt.idx = Number(d.dataset.k); renderWtStep(); });
  });
  $("wt-prev").disabled = wt.idx === 0;
  $("wt-next").disabled = wt.idx === wt.steps.length - 1;
}

function renderWtVisual(data, prev) {
  const vis = $("wt-visual");
  if (!vis) return;

  // ---- 数组 + 指针层：常驻 DOM，指针平滑滑动、格子变化弹跳 ----
  if (Array.isArray(data.array)) {
    let arr = vis.querySelector(".wt-array");
    if (!arr) {
      vis.innerHTML = "";
      arr = document.createElement("div");
      arr.className = "wt-array";
      vis.appendChild(arr);
      for (let k = 0; k < wt.arrayLen; k++) {
        const cell = document.createElement("div");
        cell.className = "wt-cell";
        cell.dataset.k = k;
        arr.appendChild(cell);
      }
      const ptrLayer = document.createElement("div");
      ptrLayer.className = "wt-ptr-layer";
      vis.appendChild(ptrLayer);
      for (const name of wt.ptrNames) {
        const p = document.createElement("div");
        p.className = "wt-ptr";
        p.dataset.ptr = name;
        ptrLayer.appendChild(p);
      }
    }
    const cells = arr.querySelectorAll(".wt-cell");
    cells.forEach((c) => {
      const k = Number(c.dataset.k);
      const v = k < data.array.length ? data.array[k] : null;
      const text = v === null ? "" : String(v);
      if (c.textContent !== text) {
        c.textContent = text;
        // 值发生变化时播放弹跳动画
        if (text !== "" && prev && Array.isArray(prev.array) && String(prev.array[k] ?? "") !== text) {
          c.classList.remove("changed");
          void c.offsetWidth;
          c.classList.add("changed");
          setTimeout(() => c.classList.remove("changed"), 600);
        }
      }
      c.classList.toggle("hl", (data.highlight || []).includes(k));
    });
    // 指针平滑滑动到新位置
    const ptrLayer = vis.querySelector(".wt-ptr-layer");
    const ptrs = ptrLayer.querySelectorAll(".wt-ptr");
    const ptrMap = data.pointers || {};
    ptrs.forEach((p) => {
      const name = p.dataset.ptr;
      if (name in ptrMap) {
        p.style.left = (Number(ptrMap[name]) * 64 + 8) + "px";
        p.innerHTML = `▼ <b>${escapeHtml(name)}</b>=${escapeHtml(String(ptrMap[name]))}`;
        p.style.opacity = "1";
      } else {
        p.style.opacity = "0";
      }
    });
  } else {
    vis.innerHTML = "";
  }

  // ---- 哈希表 / 栈 / 队列：内容变化时才重建（行级淡入） ----
  let extraHtml = "";
  if (data.map && Object.keys(data.map).length) {
    extraHtml += `<div class="wt-map"><div class="wt-map-title">🗺 哈希表</div><table><tr><th>键</th><th>值</th></tr>`;
    for (const [k, v] of Object.entries(data.map)) {
      extraHtml += `<tr class="wt-row"><td>${escapeHtml(k)}</td><td>${escapeHtml(String(v))}</td></tr>`;
    }
    extraHtml += `</table></div>`;
  }
  for (const key of ["stack", "queue"]) {
    if (Array.isArray(data[key]) && data[key].length) {
      const label = key === "stack" ? "📚 栈" : "🎢 队列";
      extraHtml += `<div class="wt-seq"><span class="wt-seq-label">${label}</span>`;
      data[key].forEach((v) => { extraHtml += `<span class="wt-seq-item">${escapeHtml(String(v))}</span>`; });
      extraHtml += `</div>`;
    }
  }
  const newKey = JSON.stringify([data.map, data.stack, data.queue]);
  if (newKey !== wt.extraKey) {
    wt.extraKey = newKey;
    const oldExtra = vis.querySelector(".wt-extra");
    if (oldExtra) oldExtra.remove();
    if (extraHtml) {
      const div = document.createElement("div");
      div.className = "wt-extra";
      div.innerHTML = extraHtml;
      vis.appendChild(div);
    }
  }
}

function wtStep(delta) {
  wt.idx = Math.min(wt.steps.length - 1, Math.max(0, wt.idx + delta));
  renderWtStep();
}

function wtTogglePlay() {
  const btn = $("wt-play");
  if (wt.timer) {
    clearInterval(wt.timer);
    wt.timer = null;
    btn.textContent = "▶ 自动播放";
    return;
  }
  if (wt.idx >= wt.steps.length - 1) { wt.idx = 0; renderWtStep(); }
  btn.textContent = "⏸ 暂停";
  wt.timer = setInterval(() => {
    if (wt.idx >= wt.steps.length - 1) {
      clearInterval(wt.timer);
      wt.timer = null;
      $("wt-play").textContent = "▶ 自动播放";
      return;
    }
    wt.idx += 1;
    renderWtStep();
  }, 2000);
}

/* ---------- 答题模板 ---------- */

async function loadTemplates() {
  if (state.templates) return state.templates;
  try {
    const resp = await fetch("/api/templates");
    state.templates = (await resp.json()).templates || {};
  } catch {
    state.templates = {};
  }
  return state.templates;
}

async function renderTemplateTab(category) {
  const el = $("tab-template");
  const templates = await loadTemplates();
  const tpl = templates[category];
  if (!tpl) {
    el.innerHTML = `<p class="problem-empty">「${escapeHtml(category)}」暂无固定模板，可查看「算法模板库」。</p>`;
    return;
  }
  el.innerHTML = `
    <div class="tpl-header">
      <h3>${escapeHtml(tpl.name)}</h3>
      <span class="tpl-when">🎯 适用场景：${escapeHtml(tpl.when)}</span>
    </div>
    <div class="code-block">
      <button class="code-copy" data-copy>📋 复制模板</button>
      <pre><code class="language-python">${escapeHtml(tpl.python)}</code></pre>
    </div>
    <p class="hint">💡 本题的「代码」标签页已按此模板框架生成，可对照学习。</p>`;
  highlightAll(el);
  el.querySelector("[data-copy]").addEventListener("click", async (e) => {
    const ok = await copyText(tpl.python);
    e.target.textContent = ok ? "✅ 已复制" : "❌ 复制失败";
    setTimeout(() => { e.target.textContent = "📋 复制模板"; }, 1500);
  });
}

async function openTemplatesLibrary() {
  const templates = await loadTemplates();
  const list = $("templates-list");
  list.innerHTML = "";
  for (const [cat, tpl] of Object.entries(templates)) {
    const div = document.createElement("div");
    div.className = "tpl-card";
    div.innerHTML = `
      <div class="tpl-card-header">
        <span class="tpl-cat">${escapeHtml(cat)}</span>
        <span class="tpl-name">${escapeHtml(tpl.name)}</span>
        <button class="btn btn-small tpl-copy" data-copy>📋 复制</button>
      </div>
      <div class="tpl-when">🎯 适用场景：${escapeHtml(tpl.when)}</div>
      <pre><code class="language-python">${escapeHtml(tpl.python)}</code></pre>`;
    div.querySelector("[data-copy]").addEventListener("click", async (e) => {
      const ok = await copyText(tpl.python);
      e.target.textContent = ok ? "✅ 已复制" : "❌";
      setTimeout(() => { e.target.textContent = "📋 复制"; }, 1200);
    });
    list.appendChild(div);
  }
  highlightAll(list);
  hide($("input-panel"));
  hide($("progress-panel"));
  hide($("result-panel"));
  hide($("error-panel"));
  show($("templates-panel"));
}

/* ---------- 标签页切换（懒渲染） ---------- */

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === name);
  });
  document.querySelectorAll(".tab-content").forEach((c) => {
    c.classList.toggle("hidden", c.id !== "tab-" + name);
  });
  if (!state.renderedTabs[name] && state.record) {
    if (name === "analysis") {
      renderAnalysisTab(state.record.analysis);
      state.renderedTabs[name] = true;
    } else if (name === "walkthrough") {
      renderWalkthroughTab(state.record.walkthrough);
      state.renderedTabs[name] = true;
    } else if (name === "flowchart") {
      renderFlowchartTab(state.record.flowchart);
      state.renderedTabs[name] = true;
    } else if (name === "code") {
      renderCodeTab(state.record.code);
      state.renderedTabs[name] = true;
    } else if (name === "template") {
      renderTemplateTab(state.record.category || "其他");
      state.renderedTabs[name] = true;
    }
  }
}

/* ---------- 历史记录（分类筛选 + 分组） ---------- */

function setActiveHistory(slug) {
  document.querySelectorAll(".history-item").forEach((li) => {
    li.classList.toggle("active", li.dataset.slug === slug);
  });
}

function makeHistoryItem(item) {
  const li = document.createElement("li");
  li.className = "history-item";
  li.dataset.slug = item.slug;
  const linkUrl = item.url || "https://leetcode.com/problems/" + item.slug + "/";
  li.innerHTML = `
    <div class="h-title">${escapeHtml(item.title)}</div>
    <div class="h-meta">
      <span>${DIFF_ZH[item.difficulty] || item.difficulty} · ${escapeHtml((item.updated_at || "").slice(0, 16))}</span>
      <span class="h-actions">
        <a class="h-link" href="${escapeHtml(linkUrl)}" target="_blank" rel="noopener" title="打开力扣原题">🔗 原题</a>
        <button class="h-del" title="删除记录">🗑</button>
      </span>
    </div>`;
  li.querySelector(".h-title").addEventListener("click", () => loadRecord(item.slug));
  // 点原题链接只跳转，不触发加载记录
  li.querySelector(".h-link").addEventListener("click", (e) => e.stopPropagation());
  li.querySelector(".h-del").addEventListener("click", async (e) => {
    e.stopPropagation();
    if (!confirm(`删除「${item.title}」的记录？`)) return;
    await fetch("/api/history/" + encodeURIComponent(item.slug), { method: "DELETE" });
    delete state.cache[item.slug];
    loadHistory();
  });
  return li;
}

function renderHistoryList(items) {
  const list = $("history-list");
  const filter = state.categoryFilter;
  const filtered = filter === "全部" ? items : items.filter((i) => (i.category || "其他") === filter);
  if (!filtered.length) {
    list.innerHTML = `<li class="history-empty">该分类下暂无记录</li>`;
    return;
  }
  list.innerHTML = "";
  if (filter === "全部") {
    const groups = {};
    for (const it of filtered) {
      const c = it.category || "其他";
      (groups[c] = groups[c] || []).push(it);
    }
    for (const [c, arr] of Object.entries(groups)) {
      const header = document.createElement("li");
      header.className = "history-group";
      header.textContent = `${c} (${arr.length})`;
      list.appendChild(header);
      for (const item of arr) list.appendChild(makeHistoryItem(item));
    }
  } else {
    for (const item of filtered) list.appendChild(makeHistoryItem(item));
  }
  if (currentSlug) setActiveHistory(currentSlug);
}

function renderCategoryFilter(items) {
  const el = $("category-filter");
  const counts = {};
  for (const it of items) {
    const c = it.category || "其他";
    counts[c] = (counts[c] || 0) + 1;
  }
  const cats = Object.keys(counts).sort();
  let html = `<button class="cat-chip${state.categoryFilter === "全部" ? " active" : ""}" data-cat="全部">全部 (${items.length})</button>`;
  for (const c of cats) {
    html += `<button class="cat-chip${state.categoryFilter === c ? " active" : ""}" data-cat="${escapeHtml(c)}">${escapeHtml(c)} (${counts[c]})</button>`;
  }
  el.innerHTML = html;
  el.querySelectorAll(".cat-chip").forEach((b) => {
    b.addEventListener("click", () => {
      state.categoryFilter = b.dataset.cat;
      el.querySelectorAll(".cat-chip").forEach((x) => x.classList.toggle("active", x === b));
      renderHistoryList(state.historyItems);
    });
  });
}

async function loadHistory() {
  try {
    const resp = await fetch("/api/history");
    const data = await resp.json();
    state.historyItems = data.items || [];
    renderCategoryFilter(state.historyItems);
    renderHistoryList(state.historyItems);
  } catch {
    /* 忽略历史加载失败 */
  }
}

async function loadRecord(slug) {
  if (state.cache[slug]) {
    renderResult(state.cache[slug]);
    showResult();
    window.history.replaceState(null, "", "?slug=" + encodeURIComponent(slug));
    return;
  }
  try {
    const resp = await fetch("/api/history/" + encodeURIComponent(slug));
    if (!resp.ok) throw new Error("记录不存在");
    const record = await resp.json();
    renderResult(record);
    showResult();
    window.history.replaceState(null, "", "?slug=" + encodeURIComponent(slug));
  } catch (err) {
    showError("加载记录失败：" + err.message);
  }
}

/* ---------- Hot 100 批量生成 ---------- */

async function initHot100(silent) {
  const btn = $("btn-hot100-init");
  if (!silent) {
    btn.textContent = "⏳ 获取中…";
    btn.disabled = true;
  }
  try {
    const resp = await fetch("/api/hot100");
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "获取失败");
    state.hot100 = data.items || [];
    const summary = $("hot100-summary");
    summary.classList.remove("hidden");
    summary.textContent = `✅ 已获取 ${state.hot100.length} 题（${data.fetched_at || ""}）`;
    $("btn-batch-start").classList.remove("hidden");
  } catch (err) {
    if (!silent) alert("获取 Hot 100 失败：" + err.message);
  } finally {
    btn.textContent = "📥 获取 Hot 100 列表";
    btn.disabled = false;
  }
}

async function startBatch() {
  if (!state.hot100) await initHot100(true);
  if (!confirm("将批量生成 Hot 100 全部题目（每题约 30~60 秒，全部完成较久，可随时停止）。已生成过的题目会重新生成并更新。确定开始？")) return;
  try {
    const resp = await fetch("/api/batch/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 100 }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "启动失败");
    show($("btn-batch-stop"));
    hide($("btn-batch-start"));
    startBatchPolling();
  } catch (err) {
    alert("启动批量生成失败：" + err.message);
  }
}

async function stopBatch() {
  await fetch("/api/batch/stop", { method: "POST" });
  stopBatchPolling();
  updateBatchUI();
}

function startBatchPolling() {
  stopBatchPolling();
  state.batchTimer = setInterval(updateBatchUI, 3000);
  updateBatchUI();
}

function stopBatchPolling() {
  if (state.batchTimer) {
    clearInterval(state.batchTimer);
    state.batchTimer = null;
  }
}

async function updateBatchUI() {
  try {
    const resp = await fetch("/api/batch");
    const b = await resp.json();
    const statusEl = $("batch-status");
    statusEl.classList.remove("hidden");
    if (b.status === "running") {
      statusEl.textContent = `⏳ ${b.done}/${b.total} · 正在生成：${b.current ? (b.current.title_cn || b.current.slug) : "…"}`;
    } else if (b.status === "done") {
      statusEl.textContent = `✅ 完成：${b.done} 成功 / ${b.failed} 失败`;
    } else if (b.status === "stopped") {
      statusEl.textContent = `⏹ 已停止：完成 ${b.done} 题`;
    } else {
      statusEl.textContent = b.message || b.status;
    }
    const prog = $("batch-progress");
    if (b.total > 0) {
      prog.classList.remove("hidden");
      $("batch-bar").style.width = Math.round(((b.done + b.failed) / b.total) * 100) + "%";
    }
    if (b.status === "running") {
      show($("btn-batch-stop"));
      hide($("btn-batch-start"));
    } else {
      hide($("btn-batch-stop"));
      show($("btn-batch-start"));
      if (b.status === "done" || b.status === "stopped") {
        stopBatchPolling();
        loadHistory();
      }
    }
  } catch {
    /* 忽略 */
  }
}

/* ---------- 初始化 ---------- */

function init() {
  if (typeof mermaid !== "undefined") {
    try { mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" }); } catch (e) {}
  }
  if (typeof marked !== "undefined") {
    try { marked.setOptions({ breaks: true, gfm: true }); } catch (e) {}
  }

  $("btn-generate").addEventListener("click", () => {
    const url = $("url-input").value.trim();
    if (!url) {
      $("url-input").focus();
      $("url-input").placeholder = "请先粘贴力扣题目链接";
      return;
    }
    submitGenerate(url);
  });

  $("url-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("btn-generate").click();
  });

  $("btn-new").addEventListener("click", () => {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    currentSlug = null;
    $("url-input").value = "";
    showInputOnly();
    window.history.replaceState(null, "", location.pathname);
  });

  $("btn-regen").addEventListener("click", () => {
    if (currentSlug) submitGenerate("https://leetcode.com/problems/" + currentSlug + "/");
  });

  $("ps-toggle").addEventListener("click", () => {
    $("problem-sticky").classList.toggle("open");
  });

  $("btn-templates").addEventListener("click", openTemplatesLibrary);
  $("btn-templates-back").addEventListener("click", showInputOnly);

  $("btn-hot100-init").addEventListener("click", () => initHot100(false));
  $("btn-batch-start").addEventListener("click", startBatch);
  $("btn-batch-stop").addEventListener("click", stopBatch);

  $("btn-mermaid-copy").addEventListener("click", async (e) => {
    const ok = await copyText($("mermaid-source-pre").textContent || "");
    e.target.textContent = ok ? "✅ 已复制" : "❌ 复制失败";
    setTimeout(() => { e.target.textContent = "📋 复制 Mermaid 源码"; }, 1500);
  });

  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => switchTab(t.dataset.tab));
  });

  document.querySelectorAll(".example").forEach((el) => {
    el.addEventListener("click", () => {
      $("url-input").value = el.dataset.url;
      submitGenerate(el.dataset.url);
    });
  });

  loadHistory();
  initHot100(true); // 静默预取 Hot 100 列表
  updateBatchUI();  // 若服务端有批量任务在跑，恢复进度显示

  // ?slug= 深链：直接加载历史记录
  const params = new URLSearchParams(location.search);
  const slug = params.get("slug");
  if (slug) {
    loadRecord(slug);
  }
}

document.addEventListener("DOMContentLoaded", init);
