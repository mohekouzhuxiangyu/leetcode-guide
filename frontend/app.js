/* 力扣算法学习助手 · 前端逻辑 */
"use strict";

const $ = (id) => document.getElementById(id);
const STAGES = ["fetch", "analyze", "flowchart", "code", "done"];
const LANG_ALIAS = {
  Python3: { label: "🐍 Python3", hl: "python" },
  Java: { label: "☕ Java", hl: "java" },
  "C++": { label: "⚙️ C++", hl: "cpp" },
};

let currentJobId = null;
let currentSlug = null;
let pollTimer = null;
let mermaidSeq = 0;

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

/* 防御性渲染：即使某个第三方库加载失败，页面也不报错、尽量降级展示 */
function highlightAll(container) {
  if (typeof hljs === "undefined") return; // 高亮库不可用则跳过
  container.querySelectorAll("pre code").forEach((c) => {
    try { hljs.highlightElement(c); } catch (e) { /* 单个代码块高亮失败不影响整体 */ }
  });
}

function renderMarkdown(text) {
  if (typeof marked !== "undefined") {
    try { return marked.parse(text); } catch (e) { /* 解析失败降级为纯文本 */ }
  }
  return `<pre style="white-space:pre-wrap;word-break:break-word;">${escapeHtml(text)}</pre>`;
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
  show($("input-panel"));
}

function showProgress() {
  hide($("input-panel"));
  hide($("result-panel"));
  hide($("error-panel"));
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
  show($("result-panel"));
}

function showError(msg) {
  hide($("input-panel"));
  hide($("progress-panel"));
  hide($("result-panel"));
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
    $("progress-steps").querySelectorAll("li").forEach((li, i) => {
      li.classList.remove("active", "done");
      const s = li.dataset.stage;
      const sIdx = STAGES.indexOf(s);
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

/* ---------- 结果渲染 ---------- */

function renderResult(record) {
  currentSlug = record.slug;
  window.__codeMap = record.code || {};
  const problem = record.problem || {};

  $("result-title").textContent = `${problem.title || record.title || record.slug} #${problem.id || ""}`;
  const diff = $("result-difficulty");
  diff.textContent = problem.difficulty || "Unknown";
  diff.className = "badge " + (problem.difficulty || "Unknown");

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

  renderProblemTab(problem, record);
  renderAnalysisTab(record.analysis);
  renderFlowchartTab(record.flowchart);
  renderCodeTab(record.code);

  switchTab("problem");
}

function renderProblemTab(problem, record) {
  const el = $("tab-problem");
  const content = (problem.content_text || "").trim();
  const snippets = problem.code_snippets || {};
  let html = "";
  if (content) {
    html += `<div>${escapeHtml(content)}</div>`;
  } else {
    html += `<div class="problem-empty">（未获取到题目原文，请查看算法解析或<a href="${escapeHtml(problem.url || record.url || "#")}" target="_blank">原题链接</a>）</div>`;
  }
  if (Object.keys(snippets).length) {
    html += `<h3 style="margin:18px 0 8px;color:var(--accent-hover);font-size:15px;">LeetCode 函数模板</h3>`;
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
  const code = mermaidCode || "";
  $("mermaid-source-pre").textContent = code;
  const container = $("mermaid-container");
  container.innerHTML = "";
  if (!code.trim()) {
    container.innerHTML = `<div class="mermaid-error">流程图生成失败。</div>`;
    return;
  }
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

/* ---------- 标签页切换 ---------- */

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === name);
  });
  document.querySelectorAll(".tab-content").forEach((c) => {
    c.classList.toggle("hidden", c.id !== "tab-" + name);
  });
}

/* ---------- 历史记录 ---------- */

async function loadHistory() {
  try {
    const resp = await fetch("/api/history");
    const data = await resp.json();
    const list = $("history-list");
    const items = data.items || [];
    if (!items.length) {
      list.innerHTML = `<li class="history-empty">暂无记录</li>`;
      return;
    }
    list.innerHTML = "";
    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "history-item";
      li.innerHTML = `
        <div class="h-title">${escapeHtml(item.title)}</div>
        <div class="h-meta">
          <span>${item.difficulty} · ${escapeHtml((item.updated_at || "").slice(0, 16))}</span>
          <button class="h-del" title="删除记录">🗑</button>
        </div>`;
      li.querySelector(".h-title").addEventListener("click", () => loadRecord(item.slug));
      li.querySelector(".h-del").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm(`删除「${item.title}」的记录？`)) return;
        await fetch("/api/history/" + encodeURIComponent(item.slug), { method: "DELETE" });
        loadHistory();
      });
      list.appendChild(li);
    });
  } catch {
    /* 忽略历史加载失败 */
  }
}

async function loadRecord(slug) {
  try {
    const resp = await fetch("/api/history/" + encodeURIComponent(slug));
    if (!resp.ok) throw new Error("记录不存在");
    const record = await resp.json();
    currentSlug = record.slug;
    renderResult(record);
    showResult();
    window.history.replaceState(null, "", "?slug=" + encodeURIComponent(slug));
  } catch (err) {
    showError("加载记录失败：" + err.message);
  }
}

/* ---------- 初始化 ---------- */

function init() {
  mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
  marked.setOptions({ breaks: true, gfm: true });

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

  // 存储当前代码映射供语言切换使用
  loadHistory();

  // ?slug= 深链：直接加载历史记录
  const params = new URLSearchParams(location.search);
  const slug = params.get("slug");
  if (slug) {
    loadRecord(slug);
  }
}

document.addEventListener("DOMContentLoaded", init);
