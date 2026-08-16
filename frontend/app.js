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
let vipQrTimer = null;

/* 会话状态：记录缓存 + 标签页懒渲染 + 分类筛选 + 批量生成 */
const state = {
  record: null,
  renderedTabs: {},
  cache: {},
  categoryFilter: "全部",
  groupFilter: "全部",
  difficultyFilter: "全部",
  searchQuery: "",
  tplFilter: "全部",
  tplQuery: "",
  groups: [],
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

/* ---------- 表单弹窗（替代原生 alert/confirm/prompt） ---------- */

function openModal(title, bodyHtml, actionsHtml) {
  $("modal-title").textContent = title;
  $("modal-body").innerHTML = bodyHtml;
  const err = $("modal-error");
  err.textContent = "";
  err.classList.add("hidden");
  $("modal-actions").innerHTML = actionsHtml;
  show($("modal-overlay"));
}

function closeModal() {
  hide($("modal-overlay"));
}

function confirmAction(title, message, onConfirm) {
  openModal(
    title,
    `<div class="modal-msg">${escapeHtml(message)}</div>`,
    `<button class="btn btn-small" id="modal-cancel">取消</button>
     <button class="btn btn-primary btn-small" id="modal-ok">确认</button>`
  );
  $("modal-cancel").addEventListener("click", closeModal);
  $("modal-ok").addEventListener("click", () => { closeModal(); onConfirm(); });
}

function promptText(title, placeholder, value, onOk) {
  openModal(
    title,
    `<input id="modal-input" class="modal-input" type="text" spellcheck="false"
            value="${escapeHtml(value || "")}" placeholder="${escapeHtml(placeholder || "")}" />`,
    `<button class="btn btn-small" id="modal-cancel">取消</button>
     <button class="btn btn-primary btn-small" id="modal-ok">确定</button>`
  );
  const input = $("modal-input");
  input.focus();
  input.select();
  $("modal-cancel").addEventListener("click", closeModal);
  $("modal-ok").addEventListener("click", () => {
    const v = input.value.trim();
    if (!v) {
      const err = $("modal-error");
      err.textContent = "内容不能为空";
      err.classList.remove("hidden");
      return;
    }
    closeModal();
    onOk(v);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("modal-ok").click();
  });
}

function toast(message, isError) {
  const t = $("toast");
  t.textContent = message;
  t.classList.remove("hidden", "toast-error");
  if (isError) t.classList.add("toast-error");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add("hidden"), 3200);
}

function modalError(msg) {
  const err = $("modal-error");
  err.textContent = msg;
  err.classList.remove("hidden");
}

/* ---------- 用户系统（注册/登录/邮箱验证） ---------- */

const TOKEN_KEY = "lc_token";
const auth = { user: null };

function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

/* 带登录态的请求（自动附加 Authorization 头） */
async function apiFetch(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  return fetch(path, { ...opts, headers });
}

function handleAuthExpired() {
  setToken("");
  auth.user = null;
  renderUserArea();
  toast("登录已过期，请重新登录", true);
}

/* VIP 是否有效 */
function isVip() {
  if (!auth.user || !auth.user.vip) return false;
  if (!auth.user.vip_expires_at) return true;
  return new Date(auth.user.vip_expires_at) > new Date();
}

/* VIP 权限门控：未登录弹登录，未开通弹捐款支持 */
function requireVip() {
  if (!auth.user) { showLoginModal(); return false; }
  if (!isVip()) { openVipPanel(); return false; }
  return true;
}

function renderUserArea() {
  const areas = document.querySelectorAll(".user-area");
  if (!areas.length) return;
  areas.forEach((el) => {
    if (auth.user) {
      const vipBadge = isVip() ? `<span class="vip-badge">👑 VIP</span>` : "";
      const usageBadge = `<span class="credits-badge" title="每日每账号最多生成 200 题（${isVip() ? "VIP 0.1 元/题" : "普通 1 元/题"}）">📊 今日 ${auth.user.today_usage || 0}/200</span>`;
      const upgradeBtn = isVip() ? "" : `<span class="ua-divider"></span><button class="ua-btn" data-act="vip">💖 升级VIP</button>`;
      const adminBtn = auth.user.is_admin ? `<span class="ua-divider"></span><button class="ua-btn" data-act="admin">👑 管理</button>` : "";
      el.innerHTML = `<div class="ua-inner">
        <span class="ua-user">👤 ${escapeHtml(auth.user.username)}</span>
        <span class="ua-badges">${vipBadge}${usageBadge}</span>
        ${upgradeBtn}
        ${adminBtn}
        <span class="ua-divider"></span>
        <button class="ua-btn ua-btn-danger" data-act="logout">退出</button>
      </div>`;
    } else {
      el.innerHTML = `<div class="ua-inner">
        <span class="ua-user ua-guest">👤 游客（可浏览 hot100）</span>
        <span class="ua-divider"></span>
        <button class="ua-btn" data-act="login">登录</button>
        <button class="ua-btn ua-btn-primary" data-act="register">注册</button>
      </div>`;
    }
  });
}

/* 收款码探测：后端返回实际存在的文件地址，前端直接设置（不依赖内联 onerror） */
async function loadQrcodes() {
  try {
    const resp = await fetch("/api/qrcodes");
    const data = await resp.json();
    const setQr = (id, url) => {
      const img = document.getElementById(id);
      const missing = document.getElementById(id + "-missing");
      if (!img) return;
      if (url) {
        img.src = url;
        img.style.display = "";
        if (missing) missing.classList.add("hidden");
      } else {
        img.style.display = "none";
        if (missing) missing.classList.remove("hidden");
      }
    };
    setQr("qr-wechat", data.wechat);
    setQr("qr-alipay", data.alipay);
  } catch {
    /* 忽略 */
  }
}

/* 👑 VIP 会员 / 支持页面（升级 VIP 自助开通） */
function openVipPanel() {
  loadQrcodes();
  const amounts = [1, 6.6, 9.9, 18.8, 66];
  const chipsEl = $("vip-donate-amounts");
  chipsEl.innerHTML = amounts
    .map((a) => `<button class="donate-amt" data-amt="${a}">¥${a}</button>`)
    .join("");
  const slider = $("donate-slider");
  const valEl = $("donate-amount-val");
  const btnAmt = $("self-upgrade-amount");
  const syncAmount = (v) => {
    const s = (Math.round(parseFloat(v) * 10) / 10).toFixed(1);
    valEl.textContent = s;
    btnAmt.textContent = s;
  };
  chipsEl.querySelectorAll(".donate-amt").forEach((b) => {
    b.addEventListener("click", () => {
      chipsEl.querySelectorAll(".donate-amt").forEach((x) => x.classList.toggle("active", x === b));
      slider.value = b.dataset.amt;
      syncAmount(slider.value);
    });
  });
  slider.addEventListener("input", () => {
    chipsEl.querySelectorAll(".donate-amt").forEach((x) => x.classList.remove("active"));
    syncAmount(slider.value);
  });
  syncAmount(slider.value);
  hide($("input-panel"));
  hide($("progress-panel"));
  hide($("result-panel"));
  hide($("error-panel"));
  hide($("templates-panel"));
  show($("vip-panel"));
}

/* 收款码图片加载失败时降级：尝试 .jpg，仍失败则隐藏并提示 */
function qrOnError(el, base) {
  if (el.src.indexOf(".jpg") === -1) {
    el.src = base + ".jpg";
  } else {
    el.style.display = "none";
    const m = document.getElementById(el.id + "-missing");
    if (m) m.classList.remove("hidden");
  }
}

/* 👑 VIP 管理（仅管理员）：开通永久 VIP / 查看今日用量 */
function showGrantModal() {
  openModal(
    "VIP 管理",
    `<div class="modal-form">
       <label class="modal-label">为捐款用户开通永久 VIP</label>
       <input id="grant-email" class="modal-input" type="email" spellcheck="false" placeholder="donor@example.com" />
       <button class="btn btn-primary btn-small" id="grant-vip-btn" style="width:100%;">👑 开通永久 VIP</button>
     </div>
     <div class="modal-form">
       <label class="modal-label">今日生成用量（计费流水）</label>
       <button class="btn btn-small" id="grant-usage-btn" style="width:100%;">📊 查看今日用量</button>
     </div>
     <div id="grant-usage-list"></div>`,
    `<button class="btn btn-small" id="modal-cancel">关闭</button>`
  );
  $("modal-cancel").addEventListener("click", closeModal);
  $("grant-vip-btn").addEventListener("click", async () => {
    const email = $("grant-email").value.trim();
    if (!email) { modalError("请输入用户邮箱"); return; }
    try {
      const resp = await apiFetch("/api/vip/grant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, mode: "vip", count: 1 }),
      });
      const data = await resp.json();
      if (!resp.ok) { modalError(data.detail || "操作失败"); return; }
      toast(data.detail || "操作成功");
    } catch (err) {
      modalError("操作失败：" + err.message);
    }
  });
  $("grant-usage-btn").addEventListener("click", async () => {
    try {
      const resp = await apiFetch("/api/vip/usage");
      const data = await resp.json();
      if (!resp.ok) { modalError(data.detail || "获取失败"); return; }
      const list = $("grant-usage-list");
      if (!data.items.length) {
        list.innerHTML = `<div class="modal-msg" style="color:var(--text-dim);font-size:12px;">今日暂无生成记录</div>`;
        return;
      }
      list.innerHTML = `<div class="modal-msg" style="font-size:12px;">今日共 <b>${data.count_today}</b> 题，应收 <b>¥${data.total_today}</b></div>
        <table class="usage-table"><tr><th>用户</th><th>题目</th><th>单价</th><th>时间</th></tr>
        ${data.items.map((i) => `<tr><td>${escapeHtml(i.email)}</td><td>${escapeHtml(i.slug)}</td><td>¥${i.price}</td><td>${escapeHtml(i.created_at)}</td></tr>`).join("")}
        </table>`;
    } catch (err) {
      modalError("获取失败：" + err.message);
    }
  });
}

function showLoginModal() {
  openModal(
    "登录",
    `<div class="modal-form">
       <label class="modal-label">邮箱</label>
       <input id="lf-email" class="modal-input" type="email" spellcheck="false" placeholder="you@example.com" />
       <label class="modal-label">密码</label>
       <input id="lf-password" class="modal-input" type="password" placeholder="密码" />
     </div>`,
    `<button class="btn btn-small" id="modal-cancel">取消</button>
     <button class="btn btn-primary btn-small" id="modal-ok">登录</button>`
  );
  $("modal-cancel").addEventListener("click", closeModal);
  $("modal-ok").addEventListener("click", async () => {
    const email = $("lf-email").value.trim();
    const password = $("lf-password").value;
    if (!email || !password) { modalError("请输入邮箱和密码"); return; }
    try {
      const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await resp.json();
      if (!resp.ok) { modalError(data.detail || "登录失败"); return; }
      setToken(data.token);
      auth.user = data.user;
      closeModal();
      renderUserArea();
      loadHistory();
      loadGroups();
      toast(`欢迎回来，${data.user.username}`);
    } catch (err) {
      modalError("登录失败：" + err.message);
    }
  });
}

function showRegisterModal() {
  openModal(
    "注册",
    `<div class="modal-form">
       <label class="modal-label">用户名</label>
       <input id="rf-username" class="modal-input" type="text" spellcheck="false" placeholder="例如：zhangsan" />
       <label class="modal-label">邮箱</label>
       <input id="rf-email" class="modal-input" type="email" spellcheck="false" placeholder="you@example.com" />
       <label class="modal-label">密码（至少 6 位）</label>
       <input id="rf-password" class="modal-input" type="password" placeholder="密码" />
       <label class="modal-label">确认密码</label>
       <input id="rf-password2" class="modal-input" type="password" placeholder="再次输入密码" />
     </div>`,
    `<button class="btn btn-small" id="modal-cancel">取消</button>
     <button class="btn btn-primary btn-small" id="modal-ok">注册</button>`
  );
  $("modal-cancel").addEventListener("click", closeModal);
  $("modal-ok").addEventListener("click", async () => {
    const username = $("rf-username").value.trim();
    const email = $("rf-email").value.trim();
    const password = $("rf-password").value;
    const password2 = $("rf-password2").value;
    if (!username || !email || !password) { modalError("请填写完整信息"); return; }
    if (password !== password2) { modalError("两次输入的密码不一致"); return; }
    try {
      const resp = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
      });
      const data = await resp.json();
      if (!resp.ok) { modalError(data.detail || "注册失败"); return; }
      closeModal();
      showVerifyInfo(data.dev_verify_url, data.message);
    } catch (err) {
      modalError("注册失败：" + err.message);
    }
  });
}

function showVerifyInfo(devUrl, message) {
  const body = devUrl
    ? `<div class="modal-msg">${escapeHtml(message)}</div>
       <div class="modal-msg">当前为开发模式（未配置 SMTP），请点击以下链接完成邮箱验证：</div>
       <a class="modal-link" href="${escapeHtml(devUrl)}" target="_blank" rel="noopener">${escapeHtml(devUrl)}</a>
       <div class="modal-msg" style="color:var(--text-dim)">验证完成后返回本页点击「登录」。</div>`
    : `<div class="modal-msg">${escapeHtml(message)}，请前往邮箱点击验证链接。</div>`;
  openModal(
    "注册成功",
    body,
    `<button class="btn btn-primary btn-small" id="modal-ok">去登录</button>`
  );
  $("modal-ok").addEventListener("click", () => { closeModal(); showLoginModal(); });
}

async function logoutUser() {
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: { "Authorization": "Bearer " + getToken() },
    });
  } catch { /* 忽略 */ }
  setToken("");
  auth.user = null;
  renderUserArea();
  state.historyItems = [];
  state.groups = [];
  renderGroupFilter();
  renderHistoryList([]);
  hide($("batch-panel"));
  toast("已退出登录");
}

async function initAuth() {
  const token = getToken();
  if (!token) { renderUserArea(); }
  else {
    try {
      const resp = await apiFetch("/api/auth/me");
      if (resp.ok) {
        auth.user = (await resp.json()).user;
      } else {
        setToken("");
      }
    } catch {
      setToken("");
    }
    renderUserArea();
  }
  // 游客也能浏览共享 hot100（后端只返回共享目录）
  loadHistory();
  loadGroups();
  updateBatchUI();
  if (auth.user) {
    // 支付宝/模拟支付跳回 ?vip=ok：刷新 VIP 状态
    const qs = new URLSearchParams(location.search);
    if (qs.get("vip") === "ok") {
      const resp = await apiFetch("/api/auth/me");
      if (resp.ok) {
        auth.user = (await resp.json()).user;
        renderUserArea();
        toast("🎉 VIP 开通成功");
      }
      window.history.replaceState(null, "", location.pathname);
    }
  }
}

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

/* 流程图缩放状态 */
const mz = { scale: 1, baseW: 0, baseH: 0 };

function mermaidApplyZoom() {
  const svg = document.querySelector("#mz-stage svg");
  const pct = $("mz-pct");
  if (!svg) return;
  svg.style.width = Math.round(mz.baseW * mz.scale) + "px";
  svg.style.height = Math.round(mz.baseH * mz.scale) + "px";
  if (pct) pct.textContent = Math.round(mz.scale * 100) + "%";
}

function mermaidFit() {
  const svg = document.querySelector("#mz-stage svg");
  const container = $("mermaid-container");
  if (!svg || !container) return;
  const w = svg.viewBox && svg.viewBox.baseVal ? svg.viewBox.baseVal.width : parseFloat(svg.getAttribute("width")) || 800;
  const h = svg.viewBox && svg.viewBox.baseVal ? svg.viewBox.baseVal.height : parseFloat(svg.getAttribute("height")) || 600;
  mz.baseW = w;
  mz.baseH = h;
  const availW = Math.max(container.clientWidth - 48, 200);
  const availH = Math.min(window.innerHeight * 0.6, 520);
  mz.scale = Math.min(availW / w, availH / h, 1);
  mermaidApplyZoom();
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
    container.innerHTML = `<div class="mz-stage" id="mz-stage">${svg}</div>`;
    const svgEl = container.querySelector("svg");
    svgEl.style.maxWidth = "none"; // 允许放大超过容器，配合滚动
    svgEl.style.display = "block";
    mermaidFit();
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
  hide($("vip-panel"));
  show($("input-panel"));
}

function showProgress() {
  hide($("input-panel"));
  hide($("result-panel"));
  hide($("error-panel"));
  hide($("templates-panel"));
  hide($("vip-panel"));
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
  hide($("vip-panel"));
  show($("result-panel"));
}

function showError(msg) {
  hide($("input-panel"));
  hide($("progress-panel"));
  hide($("result-panel"));
  hide($("templates-panel"));
  hide($("vip-panel"));
  const el = $("error-panel");
  el.textContent = msg;
  show(el);
}

/* ---------- 生成流程 ---------- */

async function submitGenerate(url) {
  if (!requireVip()) return; // 未登录弹登录，未开通 VIP 弹购买
  currentJobId = null;
  showProgress();
  try {
    const resp = await apiFetch("/api/generate", {
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
    const resp = await apiFetch("/api/jobs/" + currentJobId);
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
  const sharedNote = record.shared ? " · 🆓 免费共享题目（只读）" : "";
  $("result-time").textContent = `生成于 ${timeText} ${note}${sharedNote}`;
  // 共享目录只读：隐藏重新生成按钮
  $("btn-regen").classList.toggle("hidden", !!record.shared);

  // 固定题目描述：完整展示题目信息（描述+插图+示例+约束+函数模板），可隐藏
  const ps = $("problem-sticky");
  const hasContent = (record.problem_zh || problem.content_text || "").trim();
  if (hasContent) {
    $("ps-body").innerHTML = buildProblemHtml(problem, record);
    highlightAll($("ps-body"));
    ps.classList.remove("hidden");
    ps.classList.remove("collapsed");
  } else {
    ps.classList.add("hidden");
  }

  setActiveHistory(record.slug);
  switchTab("analysis");
}

function renderExampleBody(body) {
  /* 把示例的 输入/输出/解释 行结构化展示，避免糊成一片 */
  const lines = String(body || "").split("\n");
  let html = "";
  for (const ln of lines) {
    const m = ln.trim().match(/^(输入|输出|解释|说明|Input|Output|Explanation)\s*[:：]\s*(.*)$/);
    if (m) {
      const label = m[1];
      const value = m[2];
      if (label === "输入" || label === "Input") {
        html += `<div class="ex-row"><span class="ex-label">输入</span><code>${escapeHtml(value)}</code></div>`;
      } else if (label === "输出" || label === "Output") {
        html += `<div class="ex-row"><span class="ex-label">输出</span><code>${escapeHtml(value)}</code></div>`;
      } else {
        html += `<div class="ex-row ex-note">${escapeHtml(ln.trim())}</div>`;
      }
    } else if (ln.trim()) {
      html += `<div class="ex-row ex-note">${escapeHtml(ln.trim())}</div>`;
    }
  }
  return html;
}

function buildProblemHtml(problem, record) {
  const content = (problem.content_text || "").trim();
  const snippets = problem.code_snippets || {};
  const zh = (record.problem_zh || "").trim();
  let html = "";
  if (zh || content) {
    const { description, examples, constraints } = parseProblemSections(zh || content);
    // 描述与约束支持 Markdown（反引号/加粗/列表正确渲染），示例保持代码块
    if (description) html += `<div class="problem-desc">${renderMarkdown(description)}</div>`;
    // 原题插图
    if (Array.isArray(problem.images) && problem.images.length) {
      html += `<div class="problem-images">`;
      problem.images.forEach((src) => {
        html += `<div class="problem-image"><img src="${escapeHtml(src)}" alt="原题插图" loading="lazy" referrerpolicy="no-referrer" /></div>`;
      });
      html += `</div>`;
    }
    if (examples.length) {
      html += `<h3 class="sec-title">📌 示例</h3>`;
      for (const ex of examples) {
        html += `<div class="problem-example"><div class="example-title">${escapeHtml(ex.title)}</div>`;
        if (ex.body) html += renderExampleBody(ex.body);
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
    html += `<h3 class="sec-title">🧩 LeetCode 函数模板 <span class="sec-hint">— 提交代码时使用的函数签名（直接从 LeetCode 获取，可对照「代码」标签页的实现）</span></h3>`;
    for (const [lang, code] of Object.entries(snippets)) {
      html += `<div class="code-block"><pre><code class="language-${LANG_ALIAS[lang]?.hl || "text"}">${escapeHtml(code)}</code></pre></div>`;
    }
  }
  return html;
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
  renderTplTags(templates);
  renderTemplatesList(templates);
  hide($("input-panel"));
  hide($("progress-panel"));
  hide($("result-panel"));
  hide($("error-panel"));
  show($("templates-panel"));
}

/* 模板库顶部分类标签 */
function renderTplTags(templates) {
  const el = $("tpl-tags");
  if (!el) return;
  const keys = Object.keys(templates);
  let html = `<button class="cat-chip${state.tplFilter === "全部" ? " active" : ""}" data-tpl="__all__">全部 (${keys.length})</button>`;
  for (const k of keys) {
    html += `<button class="cat-chip${state.tplFilter === k ? " active" : ""}" data-tpl="${escapeHtml(k)}">${escapeHtml(k)}</button>`;
  }
  el.innerHTML = html;
  el.querySelectorAll(".cat-chip").forEach((b) => {
    b.addEventListener("click", () => {
      state.tplFilter = b.dataset.tpl === "__all__" ? "全部" : b.dataset.tpl;
      el.querySelectorAll(".cat-chip").forEach((x) => x.classList.toggle("active", x === b));
      renderTemplatesList(templates);
    });
  });
}

/* 模板列表：按标签 + 搜索词过滤渲染 */
function renderTemplatesList(templates) {
  const list = $("templates-list");
  if (!list) return;
  const q = (state.tplQuery || "").trim().toLowerCase();
  const entries = Object.entries(templates).filter(([cat, tpl]) => {
    if (state.tplFilter !== "全部" && cat !== state.tplFilter) return false;
    if (q) {
      const hay = `${cat} ${tpl.name || ""} ${tpl.when || ""} ${tpl.python || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  if (!entries.length) {
    list.innerHTML = `<div class="problem-empty" style="padding:30px;text-align:center;">没有匹配的模板</div>`;
    return;
  }
  list.innerHTML = "";
  for (const [cat, tpl] of entries) {
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
}

/* ---------- 题目心得（Markdown） ---------- */

async function renderNoteTab(record) {
  const container = $("tab-note");
  // 心得文档为 VIP 专属功能
  if (!isVip()) {
    container.innerHTML = `
      <div class="note-vip-gate">
        <div class="note-vip-icon">👑</div>
        <h3>心得文档为 VIP 专属功能</h3>
        <p>开通 VIP 后，可在每道题下撰写自己的 Markdown 解题心得（支持富文本预览）。</p>
        <button class="btn btn-primary" id="note-vip-btn">💖 升级 VIP</button>
      </div>`;
    container.querySelector("#note-vip-btn").addEventListener("click", openVipPanel);
    return;
  }
  const slug = record.slug;
  const editor = $("note-editor");
  const preview = $("note-preview");
  editor.value = "";
  preview.classList.add("hidden");
  preview.innerHTML = "";
  editor.classList.remove("hidden");
  $("note-preview-btn").textContent = "👁 预览";
  $("note-status").textContent = "";
  try {
    const resp = await apiFetch("/api/notes/" + encodeURIComponent(slug));
    if (resp.status === 403) { toast("心得文档为 VIP 专属功能", true); openVipPanel(); return; }
    if (resp.ok) {
      const data = await resp.json();
      editor.value = data.content || "";
      if (data.updated_at) $("note-status").textContent = "上次保存：" + data.updated_at;
    }
  } catch {
    /* 忽略 */
  }
}

function bindNoteEditor() {
  $("note-save-btn").addEventListener("click", async () => {
    if (!requireVip()) return;
    if (!state.record) return;
    const slug = state.record.slug;
    const content = $("note-editor").value || "";
    try {
      const resp = await apiFetch("/api/notes/" + encodeURIComponent(slug), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        toast(d.detail || "保存失败", true);
        return;
      }
      $("note-status").textContent = "已保存 " + new Date().toLocaleString();
      toast("心得已保存");
    } catch (err) {
      toast("保存失败：" + err.message, true);
    }
  });

  $("note-preview-btn").addEventListener("click", () => {
    const preview = $("note-preview");
    const editor = $("note-editor");
    if (preview.classList.contains("hidden")) {
      preview.innerHTML = renderMarkdown(editor.value || "");
      highlightAll(preview);
      preview.classList.remove("hidden");
      editor.classList.add("hidden");
      $("note-preview-btn").textContent = "✏️ 编辑";
    } else {
      preview.classList.add("hidden");
      editor.classList.remove("hidden");
      $("note-preview-btn").textContent = "👁 预览";
    }
  });
}

/* VIP 页面：自助开通绑定 */
function bindVipPanel() {
  $("btn-self-upgrade").addEventListener("click", async () => {
    if (!auth.user) { showLoginModal(); return; }
    const amount = parseFloat($("donate-amount-val").textContent) || 1;
    try {
      const resp = await apiFetch("/api/vip/self-upgrade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount }),
      });
      const data = await resp.json();
      if (!resp.ok) { toast(data.detail || "操作失败", true); return; }
      auth.user = data.user;
      renderUserArea();
      toast("🎉 VIP 开通成功（+%s 次）".replace("%s", data.credits_added));
      showInputOnly();
    } catch (err) {
      toast("操作失败：" + err.message, true);
    }
  });
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
    } else if (name === "note") {
      renderNoteTab(state.record);
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

/* 标题中高亮搜索关键词（安全转义后包裹 <mark>） */
function highlightTitle(title, query) {
  if (!query) return escapeHtml(title);
  const lower = title.toLowerCase();
  const q = query.toLowerCase();
  let html = "";
  let i = 0;
  let idx = lower.indexOf(q);
  while (idx !== -1 && i < title.length) {
    html += escapeHtml(title.slice(i, idx));
    html += `<mark>${escapeHtml(title.slice(idx, idx + q.length))}</mark>`;
    i = idx + q.length;
    idx = lower.indexOf(q, i);
  }
  html += escapeHtml(title.slice(i));
  return html;
}

/* 按分组 + 分类 + 难度 + 搜索词过滤历史记录 */
function filterHistoryItems(items) {
  let filtered = items;
  if (state.groupFilter !== "全部") {
    filtered = filtered.filter((i) => (i.group || "") === state.groupFilter);
  }
  if (state.categoryFilter !== "全部") {
    filtered = filtered.filter((i) => (i.category || "其他") === state.categoryFilter);
  }
  if (state.difficultyFilter !== "全部") {
    filtered = filtered.filter((i) => (i.difficulty || "Unknown") === state.difficultyFilter);
  }
  const q = state.searchQuery.trim().toLowerCase();
  if (q) {
    filtered = filtered.filter((i) => {
      const hay = `${i.title} ${i.slug} ${i.category || ""} ${(i.tags || []).join(" ")}`.toLowerCase();
      return hay.includes(q);
    });
  }
  return filtered;
}

function renderDifficultyFilter(items) {
  const el = $("difficulty-filter");
  const counts = { Easy: 0, Medium: 0, Hard: 0 };
  for (const it of items) {
    const d = it.difficulty;
    if (d in counts) counts[d]++;
  }
  const total = items.length;
  const defs = [
    ["全部", total, ""],
    ["简单", counts.Easy, "Easy"],
    ["中等", counts.Medium, "Medium"],
    ["困难", counts.Hard, "Hard"],
  ];
  let html = "";
  for (const [label, n, val] of defs) {
    const active = state.difficultyFilter === (val || "全部");
    const cls = val ? `diff-${val}` : "";
    html += `<button class="cat-chip ${cls}${active ? " active" : ""}" data-diff="${val}">${label} (${n})</button>`;
  }
  el.innerHTML = html;
  el.querySelectorAll(".cat-chip").forEach((b) => {
    b.addEventListener("click", () => {
      state.difficultyFilter = b.dataset.diff || "全部";
      el.querySelectorAll(".cat-chip").forEach((x) => x.classList.toggle("active", x === b));
      renderHistoryList(state.historyItems);
    });
  });
}

function makeHistoryItem(item) {
  const li = document.createElement("li");
  li.className = "history-item diff-" + item.difficulty;
  li.dataset.slug = item.slug;
  const linkUrl = item.url || "https://leetcode.cn/problems/" + item.slug + "/";
  const freeBadge = item.shared ? '<span class="free-badge">免费</span> ' : "";
  const delBtn = item.shared ? "" : '<button class="h-del" title="删除记录">🗑</button>';
  li.innerHTML = `
    <div class="h-title">${freeBadge}${highlightTitle(item.title, state.searchQuery.trim())}</div>
    <div class="h-meta">
      <span class="h-diff ${item.difficulty}">${DIFF_ZH[item.difficulty] || item.difficulty}</span>
      <span class="h-date">${escapeHtml((item.updated_at || "").slice(0, 16))}</span>
      <span class="h-actions">
        <a class="h-link" href="${escapeHtml(linkUrl)}" target="_blank" rel="noopener" title="打开力扣原题">🔗 原题</a>
        ${delBtn}
      </span>
    </div>`;
  li.addEventListener("click", () => loadRecord(item.slug));
  // 点原题链接只跳转，不触发加载记录
  li.querySelector(".h-link").addEventListener("click", (e) => e.stopPropagation());
  if (!item.shared) {
    li.querySelector(".h-del").addEventListener("click", (e) => {
      e.stopPropagation();
      if (!requireVip()) return; // 未开通 VIP 弹购买
      confirmAction("删除记录", `确定删除「${item.title}」？删除后不可恢复。`, async () => {
        try {
          const resp = await apiFetch("/api/history/" + encodeURIComponent(item.slug), { method: "DELETE" });
          if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            toast(data.detail || "删除失败", true);
            return;
          }
          delete state.cache[item.slug];
          loadHistory();
          loadGroups(); // 删除后刷新分组数量
          toast("已删除「" + item.title + "」");
        } catch (err) {
          toast("删除失败：" + err.message, true);
        }
      });
    });
  }
  return li;
}

function renderHistoryList(items) {
  const list = $("history-list");
  const filtered = filterHistoryItems(items);
  if (!filtered.length) {
    let msg = "暂无记录";
    if (state.searchQuery.trim()) {
      msg = "没有匹配「" + escapeHtml(state.searchQuery.trim()) + "」的题目";
    } else if (state.groupFilter !== "全部" || state.categoryFilter !== "全部" || state.difficultyFilter !== "全部") {
      msg = "该条件下暂无记录";
    }
    list.innerHTML = `<li class="history-empty">${msg}</li>`;
    return;
  }
  list.innerHTML = "";
  if (state.categoryFilter === "全部") {
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
    const resp = await apiFetch("/api/history");
    if (resp.status === 401) { handleAuthExpired(); return; }
    if (!resp.ok) return;
    const data = await resp.json();
    state.historyItems = data.items || [];
    renderCategoryFilter(state.historyItems);
    renderDifficultyFilter(state.historyItems);
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
    const resp = await apiFetch("/api/history/" + encodeURIComponent(slug));
    if (!resp.ok) throw new Error("记录不存在");
    const record = await resp.json();
    renderResult(record);
    showResult();
    window.history.replaceState(null, "", "?slug=" + encodeURIComponent(slug));
  } catch (err) {
    showError("加载记录失败：" + err.message);
  }
}

/* ---------- 分组 ---------- */

async function loadGroups() {
  try {
    const resp = await apiFetch("/api/groups");
    if (resp.status === 401) { handleAuthExpired(); return; }
    if (!resp.ok) return;
    const data = await resp.json();
    state.groups = data.groups || [];
    renderGroupFilter();
    populateGroupSelect();
  } catch {
    /* 忽略 */
  }
}

function renderGroupFilter() {
  const el = $("group-filter");
  let html = `<button class="cat-chip${state.groupFilter === "全部" ? " active" : ""}" data-grp="__all__">全部 (${state.historyItems.length})</button>`;
  for (const g of state.groups) {
    const name = g.name || "未分组";
    html += `<button class="cat-chip${state.groupFilter === g.name ? " active" : ""}" data-grp="${escapeHtml(g.name)}">${escapeHtml(name)} (${g.count})</button>`;
  }
  el.innerHTML = html;
  el.querySelectorAll(".cat-chip").forEach((b) => {
    b.addEventListener("click", () => {
      state.groupFilter = b.dataset.grp === "__all__" ? "全部" : b.dataset.grp;
      el.querySelectorAll(".cat-chip").forEach((x) => x.classList.toggle("active", x === b));
      renderHistoryList(state.historyItems);
    });
  });
}

function populateGroupSelect() {
  const sel = $("batch-group-select");
  if (!sel) return;
  let html = `<option value="">未分组</option>`;
  for (const g of state.groups) {
    if (!g.name) continue;
    html += `<option value="${escapeHtml(g.name)}">${escapeHtml(g.name)}（${g.count}）</option>`;
  }
  sel.innerHTML = html;
  updateBatchGroupHint();
}

/* 批量分组提示：实时显示选中的分组 */
function updateBatchGroupHint() {
  const hint = $("batch-group-hint");
  const sel = $("batch-group-select");
  if (!hint || !sel) return;
  hint.textContent = sel.value || "未分组";
}

function bindBatchGroupHint() {
  const sel = $("batch-group-select");
  if (sel) sel.addEventListener("change", updateBatchGroupHint);
}

async function createGroup() {
  if (!requireVip()) return;
  promptText("新建分组", "输入分组名称", "", async (name) => {
    try {
      const resp = await apiFetch("/api/groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const data = await resp.json();
      if (!resp.ok) { toast(data.detail || "创建分组失败", true); return; }
      if (data.ok === false) { toast(`分组「${name}」已存在`, true); return; }
      await loadGroups();
      // 默认选中新分组
      state.groupFilter = name;
      renderGroupFilter();
      renderHistoryList(state.historyItems);
      // 同步到批量分组下拉
      const sel = $("batch-group-select");
      if (sel) { sel.value = name; updateBatchGroupHint(); }
      toast(`已创建分组「${name}」`);
    } catch (err) {
      toast("创建分组失败：" + err.message, true);
    }
  });
}

/* ---------- 批量生成（链接列表 + 分组） ---------- */

async function startBatch() {
  if (!requireVip()) return;
  const urls = ($("urls-input").value || "")
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);
  if (!urls.length) {
    toast("请先粘贴题目链接（每行一个）", true);
    return;
  }
  const group = $("batch-group-select").value || "";
  confirmAction(
    "批量生成",
    `将批量生成 ${urls.length} 道题（每题约 30~60 秒，可随时停止），归入分组「${group || "未分组"}」。确定开始？`,
    async () => {
      try {
        const resp = await apiFetch("/api/batch/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ urls, group }),
        });
        const data = await resp.json();
        if (!resp.ok) { toast(data.detail || "启动失败", true); return; }
        if (data.invalid_count) toast(`有 ${data.invalid_count} 个链接无法解析（需包含 /problems/ 路径），已跳过`, true);
        startBatchPolling();
      } catch (err) {
        toast("启动批量生成失败：" + err.message, true);
      }
    }
  );
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
    const panel = $("batch-panel");
    const statusEl = $("batch-status");
    if (b.status === "running") {
      panel.classList.remove("hidden");
      statusEl.textContent = `⏳ ${b.done}/${b.total} · 正在生成：${b.current ? b.current.slug : "…"}`;
    } else if (b.status === "done" || b.status === "stopped") {
      stopBatchPolling();
      panel.classList.remove("hidden");
      statusEl.textContent = b.status === "done"
        ? `✅ 完成：${b.done} 成功 / ${b.failed} 失败`
        : `⏹ 已停止：完成 ${b.done} 题`;
      loadHistory();
      loadGroups();
      // 3 秒后若没有新任务则自动收起
      setTimeout(() => {
        fetch("/api/batch")
          .then((r) => r.json())
          .then((x) => { if (x.status !== "running") panel.classList.add("hidden"); })
          .catch(() => {});
      }, 3000);
    } else {
      panel.classList.add("hidden");
      return;
    }
    const prog = $("batch-progress");
    if (b.total > 0) {
      prog.classList.remove("hidden");
      $("batch-bar").style.width = Math.round(((b.done + b.failed) / b.total) * 100) + "%";
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

  // 主题：暗夜/白日（切换时直接替换主题 CSS 文件 + 代码高亮主题文件）
  function applyThemeFile(theme) {
    const link = $("theme-css");
    if (link) link.href = "/assets/theme-" + theme + ".css?v=1";
    const hl = $("hljs-theme");
    if (hl) hl.href = "/assets/vendor/github" + (theme === "light" ? "" : "-dark") + ".min.css";
  }
  const savedTheme = localStorage.getItem("lc_theme") || "dark";
  document.documentElement.dataset.theme = savedTheme;
  applyThemeFile(savedTheme);
  $("btn-theme").textContent = savedTheme === "dark" ? "🌙" : "☀️";
  $("btn-theme").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("lc_theme", next);
    $("btn-theme").textContent = next === "dark" ? "🌙" : "☀️";
    applyThemeFile(next);
  });

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
    if (!requireVip()) return;
    if (currentSlug && !(state.record && state.record.shared)) {
      submitGenerate("https://leetcode.cn/problems/" + currentSlug + "/");
    }
  });

  $("ps-toggle").addEventListener("click", () => {
    $("problem-sticky").classList.toggle("collapsed");
  });

  $("btn-templates").addEventListener("click", openTemplatesLibrary);
  $("btn-templates-back").addEventListener("click", showInputOnly);
  $("btn-vip-back").addEventListener("click", showInputOnly);
  bindVipPanel();
  // 模板库搜索
  $("tpl-search").addEventListener("input", () => {
    state.tplQuery = $("tpl-search").value;
    if (state.templates) renderTemplatesList(state.templates);
  });

  // 右上角用户中心：事件委托（data-act 路由），避免选择器错配导致点击无反应
  document.querySelectorAll(".user-area").forEach((area) => {
    area.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      const act = btn.dataset.act;
      if (act === "login") showLoginModal();
      else if (act === "register") showRegisterModal();
      else if (act === "logout") logoutUser();
      else if (act === "vip") openVipPanel();
      else if (act === "admin") showGrantModal();
    });
  });

  // 分组
  $("btn-add-group").addEventListener("click", createGroup);
  // 输入区标签页：单条生成 / 批量生成
  document.querySelectorAll(".input-tab").forEach((t) => {
    t.addEventListener("click", () => {
      document.querySelectorAll(".input-tab").forEach((x) => x.classList.toggle("active", x === t));
      const name = t.dataset.inputTab;
      $("input-single").classList.toggle("hidden", name !== "single");
      $("input-batch").classList.toggle("hidden", name !== "batch");
    });
  });
  $("btn-batch-start").addEventListener("click", startBatch);
  $("btn-batch-stop").addEventListener("click", stopBatch);
  bindBatchGroupHint();

  // 题目心得编辑器
  bindNoteEditor();

  $("btn-mermaid-copy").addEventListener("click", async (e) => {
    const ok = await copyText($("mermaid-source-pre").textContent || "");
    e.target.textContent = ok ? "✅ 已复制" : "❌ 复制失败";
    setTimeout(() => { e.target.textContent = "📋 复制 Mermaid 源码"; }, 1500);
  });

  // 流程图缩放控制
  $("mz-in").addEventListener("click", () => { mz.scale = Math.min(4, mz.scale * 1.25); mermaidApplyZoom(); });
  $("mz-out").addEventListener("click", () => { mz.scale = Math.max(0.2, mz.scale / 1.25); mermaidApplyZoom(); });
  $("mz-reset").addEventListener("click", () => { mz.scale = 1; mermaidApplyZoom(); });
  $("mz-fit").addEventListener("click", mermaidFit);

  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => switchTab(t.dataset.tab));
  });

  document.querySelectorAll(".example").forEach((el) => {
    el.addEventListener("click", () => {
      $("url-input").value = el.dataset.url;
      submitGenerate(el.dataset.url);
    });
  });

  // 历史题目搜索（实时过滤，支持 Esc 清空）
  const searchInput = $("search-input");
  searchInput.addEventListener("input", () => {
    state.searchQuery = searchInput.value;
    renderHistoryList(state.historyItems);
  });
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      searchInput.value = "";
      state.searchQuery = "";
      renderHistoryList(state.historyItems);
      searchInput.blur();
    }
  });

  loadHistory();
  loadGroups();
  initAuth();  // 认证初始化：恢复登录态并加载数据
  loadQrcodes(); // 收款码探测（兼容大小写扩展名）

  // ?slug= 深链：直接加载历史记录
  const params = new URLSearchParams(location.search);
  const slug = params.get("slug");
  if (slug) {
    loadRecord(slug);
  }
}

document.addEventListener("DOMContentLoaded", init);
