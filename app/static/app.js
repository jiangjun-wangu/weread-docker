const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let currentBooks = [];
let bookMetaMap = {};
let _localCancelled = new Set();
let downloadSSE = null;
let logsSSE = null;

// ---------- 工具 ----------
function toast(msg, duration = 2500) {
  const el = $("#toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden", "toast-success", "toast-error");
  if (/失败|错误|不支持|非法|error/i.test(msg)) el.classList.add("toast-error");
  else if (/成功|已保存|已删除|已启动|已完成/.test(msg)) el.classList.add("toast-success");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), duration);
}

function alertBox(msgHtml) {
  return new Promise((resolve) => {
    const ov = $("#modal-overlay");
    const ok = $("#modal-ok");
    const cancel = $("#modal-cancel");
    $("#modal-msg").innerHTML = msgHtml;
    cancel.classList.add("hidden");
    ov.classList.remove("hidden");
    ok.focus();
    function cleanup() {
      ov.classList.add("hidden");
      cancel.classList.remove("hidden");
      ok.removeEventListener("click", onOk);
      ov.removeEventListener("click", onOv);
      document.removeEventListener("keydown", onKey);
    }
    function onOk() { cleanup(); resolve(true); }
    function onOv(e) { if (e.target === ov) onOk(); }
    function onKey(e) { if (e.key === "Escape" || e.key === "Enter") onOk(); }
    ok.addEventListener("click", onOk);
    ov.addEventListener("click", onOv);
    document.addEventListener("keydown", onKey);
  });
}

function confirmBox(msg) {
  return new Promise((resolve) => {
    const ov = $("#modal-overlay");
    const ok = $("#modal-ok");
    const cancel = $("#modal-cancel");
    $("#modal-msg").textContent = msg;
    ov.classList.remove("hidden");
    ok.focus();

    function cleanup() {
      ov.classList.add("hidden");
      ok.removeEventListener("click", onOk);
      cancel.removeEventListener("click", onCancel);
      ov.removeEventListener("click", onOv);
      document.removeEventListener("keydown", onKey);
    }
    function onOk() { cleanup(); resolve(true); }
    function onCancel() { cleanup(); resolve(false); }
    function onOv(e) { if (e.target === ov) onCancel(); }
    function onKey(e) { if (e.key === "Escape") onCancel(); }

    ok.addEventListener("click", onOk);
    cancel.addEventListener("click", onCancel);
    ov.addEventListener("click", onOv);
    document.addEventListener("keydown", onKey);
  });
}

function showLoading() {
  const el = document.getElementById("global-loading");
  if (el) el.classList.remove("hidden");
}
function hideLoading() {
  const el = document.getElementById("global-loading");
  if (el) el.classList.add("hidden");
}

async function api(path, opts = {}) {
  const useLoading = opts.loading === true;
  if (useLoading) showLoading();
  try {
    const r = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json()).detail || detail; } catch (e) {}
      const err = new Error(detail);
      err.status = r.status;
      throw err;
    }
    return r.json();
  } finally {
    if (useLoading) hideLoading();
  }
}

// ---------- Tab 切换 ----------
function switchTab(name) {
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
  if (name === "logs") startLogs();
  if (name === "records") loadRecords();
  if (name === "settings") loadSettings();
  if (name === "me") loadMe();
  if (name === "upload") loadOutputs();
  if (name === "shelf") loadShelf();
}

$$(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

// ---------- 状态 ----------
async function refreshStatus() {
  try {
    const s = await api("/api/status");
    const badge = $("#login-status");
    if (s.logged_in) {
      badge.textContent = "已登录";
      badge.className = "badge ok";
      hideLoginOverlay();
    } else {
      badge.textContent = "未登录";
      badge.className = "badge err";
      showLoginOverlay();
    }
    const rateEl = $("#rate-info");
    rateEl.textContent = `本月已下 ${s.used} 本`;
    rateEl.dataset.tip = `防止频繁请求微信读书被风控封号，1 个月最多下 ${s.limit} 本`;
    rateEl.classList.remove("warn", "full");
    const pct = s.limit > 0 ? s.used / s.limit : 0;
    if (pct >= 1) rateEl.classList.add("full");
    else if (pct >= 0.8) rateEl.classList.add("warn");
    if (s.download && s.download.running) {
      renderProgress(s.download);
      if (!downloadSSE) startDownloadSSE();
    }

  } catch (e) {
    console.error(e);
  }
}
function showLoginOverlay() {
  const ov = $("#login-overlay");
  if (!ov.classList.contains("hidden")) return;
  ov.classList.remove("hidden");
  startOverlayLogin();
}

function hideLoginOverlay() {
  $("#login-overlay").classList.add("hidden");
}

async function startOverlayLogin() {
  $("#overlay-status").textContent = "正在获取二维码...";
  $("#overlay-qr").src = "";
  $("#btn-retry-qr").classList.add("hidden");
  try {
    const data = await api("/api/login/start", { method: "POST" });
    $("#overlay-qr").src = "data:image/png;base64," + data.qr;
    $("#overlay-status").textContent = "等待扫码...";
    pollOverlayLogin();
  } catch (e) {
    $("#overlay-status").textContent = "获取二维码失败：" + e.message;
    $("#btn-retry-qr").classList.remove("hidden");
  }
}

function pollOverlayLogin() {
  const t = setInterval(async () => {
    try {
      const r = await api("/api/login/poll");
      if (r.confirmed) {
        clearInterval(t);
        $("#overlay-status").textContent = "登录成功！";
        setTimeout(() => {
          hideLoginOverlay();
          switchTab("me");
          refreshStatus();
          loadShelf();
          loadMe(true);
        }, 800);
      }
    } catch (e) {}
  }, 2000);
}
// ---------- 书架 ----------
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;",
  }[c]));
}

function getSelectedIds() {
  const ids = [];
  $$("#shelf-list .book-card.selected").forEach((c) => {
    if (c.dataset.id) ids.push(c.dataset.id);
  });
  return ids;
}

// ---------- 下载 ----------
async function startDownload() {
  const ids = getSelectedIds();
  if (!ids.length) return toast("请先勾选要下载的书");
  try {
    await api("/api/download", {
      method: "POST",
      body: JSON.stringify({ book_ids: ids }),
      loading: true,
    });
    _localCancelled.clear();
    $$("#shelf-list .book-card.selected").forEach((c) => c.classList.remove("selected"));
    toast(`已启动下载任务（${ids.length} 本）`);
    startDownloadSSE();
  } catch (e) {
    toast("启动失败：" + e.message);
  }
}

function renderProgress(d) {
  window._lastDlState = d;
  renderQueueState(d);
}

function renderQueueState(d) {
  const run = !!d.running;
  window._dlRunning = run;
  const shelfList = $("#shelf-list");
  if (shelfList) shelfList.classList.toggle("dl-active", run);
  const btn = $("#btn-download-selected");
  if (btn) {
    btn.textContent = run ? "取消全部" : "下载选中";
    btn.classList.toggle("danger", run);
    btn.classList.toggle("primary", !run);
  }
  ["btn-refresh-shelf", "btn-select-all", "btn-select-none"].forEach((id) => {
    const e = document.getElementById(id);
    if (e) e.disabled = run;
  });
  ["shelf-search", "shelf-sort", "shelf-order", "shelf-filter"].forEach((id) => {
    const e = document.getElementById(id);
    if (e) e.disabled = run;
  });
  $$("#shelf-list .book-card").forEach((c) => {
    c.classList.remove("q-pending", "q-downloading", "q-done", "q-failed", "q-cancelled");
    const wrap = c.querySelector(".card-cover-wrap");
    if (wrap) wrap.querySelectorAll(".dl-ring, .q-badge, .q-cancel").forEach((e) => e.remove());
  });
  const queue = d.queue || [];
  queue.forEach((q) => {
    if (_localCancelled.has(q.bookId)) return;
    const card = document.querySelector('#shelf-list .book-card[data-id="' + q.bookId + '"]');
    if (!card) return;
    const wrap = card.querySelector(".card-cover-wrap");
    if (!wrap) return;
    const ud = card.querySelector(".card-badge.undownloaded");
    if (ud) ud.remove();
    if (q.status === "pending") {
      card.classList.add("q-pending");
      const b = document.createElement("span");
      b.className = "q-badge q-badge-pending";
      b.textContent = "排队";
      wrap.appendChild(b);
      appendCancelBtn(wrap, q.bookId);
    } else if (q.status === "downloading") {
      card.classList.add("q-downloading");
      const pct = q.pct || 0;
      const ring = document.createElement("div");
      ring.className = "dl-ring";
      ring.innerHTML =
        '<svg viewBox="0 0 36 36">' +
        '<circle cx="18" cy="18" r="15.9" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="3"/>' +
        '<circle cx="18" cy="18" r="15.9" fill="none" stroke="#fff" stroke-width="3" ' +
        'stroke-dasharray="100" stroke-dashoffset="' + (100 - pct) + '" ' +
        'transform="rotate(-90 18 18)" stroke-linecap="round"/>' +
        '</svg>' +
        '<span class="ring-pct">' + pct + '%</span>';
      wrap.appendChild(ring);
      appendCancelBtn(wrap, q.bookId);
    } else if (q.status === "failed") {
      card.classList.add("q-failed");
      const b = document.createElement("span");
      b.className = "q-badge q-badge-failed";
      b.textContent = "失败";
      wrap.appendChild(b);
    } else if (q.status === "done") {
      card.classList.add("q-done");
    } else if (q.status === "cancelled") {
      // 已取消：保持默认态，什么都不加
    }
  });
}

function startDownloadSSE() {
  if (downloadSSE) downloadSSE.close();
  downloadSSE = new EventSource("/api/download/stream");
  downloadSSE.onmessage = (ev) => {
    try {
      const d = JSON.parse(ev.data);
      renderProgress(d);
      if (!d.running && d.total > 0) {
        setTimeout(() => {
          refreshStatus();
          loadShelf();
        }, 1500);
        downloadSSE.close();
        downloadSSE = null;
      }
    } catch (e) {}
  };
  downloadSSE.addEventListener("done", () => {
    downloadSSE.close();
    downloadSSE = null;
  });
  downloadSSE.onerror = () => {
    downloadSSE.close();
    downloadSSE = null;
  };
}

// ---------- 已下载 ----------
async function loadRecords() {
  const list = $("#records-list");
  list.innerHTML = "<div class='shelf-empty'>加载中...</div>";
  try {
    const q = new URLSearchParams(recordsQuery).toString();
    const data = await api("/api/records?" + q);
    list.innerHTML = "";
    if (!data.items.length) {
      list.innerHTML = "<div class='shelf-empty'>暂无记录</div>";
      return;
    }
    data.items.forEach((r) => {
      const meta = bookMetaMap[r.bookId] || {};
      const cover = meta.cover;
      const card = document.createElement("div");
      card.className = "book-card record-card done";
      card.dataset.id = r.bookId;
      const date = r.finished_at ? new Date(r.finished_at * 1000).toLocaleString("zh-CN") : "";
      const coverHtml = cover
        ? '<img class="card-cover" src="' + escapeHtml(cover) + '" alt="" loading="lazy">'
        : '<div class="card-cover card-cover-empty"></div>';
      card.innerHTML =
        '<div class="card-cover-wrap">' + coverHtml +
        '<span class="card-badge">已下载</span>' +
        '<button class="card-del" data-id="' + escapeHtml(r.bookId) + '" title="仅移除记录（保留文件）">\u2715</button>' +
        '<button class="card-delfile" data-id="' + escapeHtml(r.bookId) + '" title="删除记录 + 文件">\u232b</button>' +
        '</div>' +
        '<div class="card-title">' + escapeHtml(r.title || r.bookId) + '</div>' +
        '<div class="card-author">' + (r.chapters || 0) + ' 章 · ' + date + '</div>';
      list.appendChild(card);
    });
    $$(".card-del").forEach((b) => {
      b.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        if (!(await confirmBox("仅移除记录，保留 EPUB 文件。继续？"))) return;
        await api("/api/records/" + encodeURIComponent(b.dataset.id), { method: "DELETE", loading: true });
        loadRecords();
        loadShelf();
      });
    });
    $$(".card-delfile").forEach((b) => {
      b.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        if (!(await confirmBox("删除记录 + 删除 EPUB 文件？此操作不可恢复！"))) return;
        await api("/api/records/" + encodeURIComponent(b.dataset.id) + "/file", { method: "DELETE", loading: true });
        loadRecords();
        loadShelf();
      });
    });
    bindIntro(list, ".record-card", "id", "below");
    renderPagerGeneric("records-pager", data, (p) => { recordsQuery.page = p; loadRecords(); });
  } catch (e) {
    if (e.status === 401) { showLoginOverlay(); list.innerHTML = ""; return; }
    list.innerHTML = "<div class='shelf-empty'>加载失败：" + escapeHtml(e.message) + "</div>";
  }
}

// ---------- 设置 ----------
async function loadSettings() {
  try {
    const s = await api("/api/config");
    $("#set-interval").value = s.download_interval || 3;
    $("#set-limit").value = s.max_per_month || 100;
    $("#set-auto-sync").checked = !!s.auto_sync_enabled;
    $("#set-sync-interval").value = s.auto_sync_interval_hours || 6;
    $("#set-sync-max").value = (s.auto_sync_max_per_run == null) ? 10 : s.auto_sync_max_per_run;
    $("#set-auto-restore").checked = !!s.auto_restore_enabled;
    $("#set-output").value = s.output_dir || "";
    $("#set-opds-enabled").checked = !!s.opds_enabled;
    $("#set-opds-user").value = s.opds_user || "";
    $("#set-opds-pass").value = s.opds_pass || "";
    $("#set-opds-url").value = location.origin + "/opds";
    $("#set-log-size").value = s.log_buffer_size || 500;
    $("#set-log-max-mb").value = s.log_file_max_mb || 10;
    $("#set-log-backups").value = s.log_file_backups || 3;
  } catch (e) {
    toast("加载设置失败：" + e.message);
  }
}

async function saveSettings() {
  try {
    await api("/api/config", {
      method: "PUT",
      body: JSON.stringify({
        download_interval: Number($("#set-interval").value),
        max_per_month: Number($("#set-limit").value),
        auto_sync_enabled: $("#set-auto-sync").checked,
        auto_sync_interval_hours: Number($("#set-sync-interval").value) || 6,
        auto_sync_max_per_run: Number($("#set-sync-max").value) || 0,
        auto_restore_enabled: $("#set-auto-restore").checked,
        log_buffer_size: Number($("#set-log-size").value) || 500,
        log_file_max_mb: Number($("#set-log-max-mb").value) || 10,
        log_file_backups: Number($("#set-log-backups").value) || 3,
        opds_enabled: $("#set-opds-enabled").checked,
        opds_user: $("#set-opds-user").value.trim(),
        opds_pass: $("#set-opds-pass").value,
      }),
    });
    toast("已保存");
  } catch (e) {
    toast("保存失败：" + e.message);
  }
}

async function startLogin() {
  try {
    const data = await api("/api/login/start", { method: "POST" });
    $("#login-qr").classList.remove("hidden");
    $("#qr-img").src = "data:image/png;base64," + data.qr;
    $("#qr-status").textContent = "等待扫码...";
    pollLogin();
  } catch (e) {
    toast("获取二维码失败：" + e.message);
  }
}

function pollLogin() {
  const t = setInterval(async () => {
    try {
      const r = await api("/api/login/poll");
      if (r.confirmed) {
        clearInterval(t);
        $("#qr-status").textContent = "登录成功！";
        setTimeout(() => {
          $("#login-qr").classList.add("hidden");
          refreshStatus();
          loadShelf();
          loadMe(true);
        }, 1500);
      }
    } catch (e) {}
  }, 2000);
}

async function logout() {
  if (!(await confirmBox("确认清除登录状态？"))) return;
  await api("/api/logout", { method: "POST" });
  toast("已清除");
  refreshStatus();
}

// ---------- 日志 ----------
function startLogs() {
  const box = $("#log-box");
  if (logsSSE) logsSSE.close();
  logsSSE = new EventSource("/api/logs/stream");
  logsSSE.onmessage = (ev) => {
    const line = JSON.parse(ev.data);
    box.textContent += line + "\n";
    box.scrollTop = box.scrollHeight;
    if (box.textContent.length > 100000) {
      box.textContent = box.textContent.slice(-50000);
    }
  };
}

// ---------- 绑定 ----------
$("#btn-refresh-shelf").addEventListener("click", () => loadShelf(true));
$("#btn-select-all").addEventListener("click", () => {
  $$("#shelf-list .book-card:not(.done)").forEach((c) => c.classList.add("selected"));
});
$("#btn-select-none").addEventListener("click", () => {
  $$("#shelf-list .book-card").forEach((c) => c.classList.remove("selected"));
});
$("#btn-download-selected").addEventListener("click", async () => {
  if (window._dlRunning) {
    if (!(await confirmBox("确认取消全部下载？"))) return;
    try {
      // 先把当前队列所有 bookId 加入本地取消集合（防 SSE 推回）
      const _q = (window._lastDlState && window._lastDlState.queue) || [];
      _q.forEach((it) => { if (it.bookId) _localCancelled.add(it.bookId); });
      await api("/api/download/cancel", { method: "POST", loading: true });
      // 乐观清空：立即移除所有卡片队列 UI
      $$("#shelf-list .book-card").forEach((c) => {
        c.classList.remove("q-pending", "q-downloading", "q-failed");
        const wrap = c.querySelector(".card-cover-wrap");
        if (wrap) wrap.querySelectorAll(".dl-ring, .q-badge, .q-cancel").forEach((e) => e.remove());
      });
      // 手动切回「下载选中」
      window._dlRunning = false;
      const _b = $("#btn-download-selected");
      if (_b) { _b.textContent = "下载选中"; _b.classList.remove("danger"); _b.classList.add("primary"); }
      toast("已请求取消全部");
    } catch (e) { toast("取消失败：" + e.message); }
  } else {
    startDownload();
  }
});
$("#btn-refresh-records").addEventListener("click", loadRecords);
(function initCopyOpds() {
  const btn = document.getElementById("btn-copy-opds");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const url = document.getElementById("set-opds-url").value;
    try {
      await navigator.clipboard.writeText(url);
      toast("已复制：" + url);
    } catch (e) {
      const inp = document.getElementById("set-opds-url");
      inp.select();
      document.execCommand("copy");
      toast("已复制");
    }
  });
})();
$("#btn-save-settings").addEventListener("click", saveSettings);
$("#btn-sync-now").addEventListener("click", async () => {
  const reasonMap = {
    busy: "已有下载任务在进行",
    not_logged_in: "未登录",
    session_expired: "登录已过期，请重新扫码",
    shelf_error: "获取书架失败",
    no_new: "没有新书",
  };
  try {
    toast("正在检查新书...");
    const r = await api("/api/sync/now", { method: "POST" });
    if (r.queued > 0) toast("发现 " + r.queued + " 本新书，已开始下载");
    else toast(reasonMap[r.reason] || "没有新书");
  } catch (e) {
    toast("检查失败：" + e.message);
  }
});
$("#btn-relogin").addEventListener("click", startLogin);
$("#btn-logout").addEventListener("click", logout);
$("#btn-clear-logs").addEventListener("click", () => {
  $("#log-box").textContent = "";
});

// ---------- 启动 ----------
refreshStatus();

$("#btn-retry-qr").addEventListener("click", startOverlayLogin);
// setInterval(refreshStatus, 10000);
let shelfQuery = { sort: "recent", order: "desc", filter: "all", q: "", page: 1, page_size: 30 };

async function loadShelf(force) {
  const list = $("#shelf-list");
  list.innerHTML = "<div class=\"shelf-empty\">加载中...</div>";
  const params = { ...shelfQuery };
  if (force) params.nocache = 1;
  const q = new URLSearchParams(params).toString();
  try {
    const data = await api("/api/shelf?" + q);
    currentBooks = data.books;
    currentBooks.forEach((b) => { bookMetaMap[b.bookId] = b; });
    list.innerHTML = "";
    if (!currentBooks.length) {
      list.innerHTML = "<div class=\"shelf-empty\">书架为空</div>";
      renderPager(data);
      return;
    }
    currentBooks.forEach((b) => {
      const card = document.createElement("div");
      card.className = "book-card";
      card.dataset.id = b.bookId;
      const isDone = b.downloaded || b.has_file;
      if (isDone) card.classList.add("done");
      const cover = b.cover
        ? '<img class="card-cover" src="' + escapeHtml(b.cover) + '" alt="" loading="lazy">'
        : '<div class="card-cover card-cover-empty"></div>';
      const badge = isDone
        ? '<span class="card-badge">已下载</span>'
        : '<span class="card-badge undownloaded">未下载</span>';
      card.innerHTML =
        '<div class="card-cover-wrap">' + cover +
        '<div class="card-check">\u2713</div>' + badge + '</div>' +
        '<div class="card-title">' + escapeHtml(b.title) + '</div>' +
        '<div class="card-author">' + escapeHtml(b.author || "未知作者") + '</div>';
      if (!isDone) {
        card.addEventListener("click", () => card.classList.toggle("selected"));
      }
      list.appendChild(card);
    });
    renderPager(data);
    bindIntro(list, ".book-card", "id", "below");
    if (window._lastDlState) renderQueueState(window._lastDlState);
  } catch (e) {
    if (e.status === 401) {
      showLoginOverlay();
      list.innerHTML = "";
      return;
    }
    list.innerHTML = "<div class=\"shelf-empty\">加载失败：" + escapeHtml(e.message) + "</div>";
  }
}

function renderPager(data) {
  const pager = $("#shelf-pager");
  if (!pager) return;
  const total = data.total || 0;
  const pages = data.total_pages || 1;
  const page = data.page || 1;
  if (pages <= 1) { pager.innerHTML = "共 " + total + " 本"; return; }
  let html = "";
  html += "<button data-p=\"" + (page - 1) + "\" " + (page <= 1 ? "disabled" : "") + ">上一页</button>";
  html += "<span class=\"pager-info\">" + page + " / " + pages + "（共 " + total + " 本）</span>";
  html += "<button data-p=\"" + (page + 1) + "\" " + (page >= pages ? "disabled" : "") + ">下一页</button>";
  pager.innerHTML = html;
  pager.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      shelfQuery.page = Number(btn.dataset.p);
      loadShelf();
    });
  });
}

const _selSort = document.getElementById("shelf-sort");
const _selOrder = document.getElementById("shelf-order");
const _selFilter = document.getElementById("shelf-filter");
if (_selSort) _selSort.addEventListener("change", () => { shelfQuery.sort = _selSort.value; shelfQuery.page = 1; loadShelf(); });
if (_selOrder) _selOrder.addEventListener("change", () => { shelfQuery.order = _selOrder.value; shelfQuery.page = 1; loadShelf(); });
if (_selFilter) _selFilter.addEventListener("change", () => { shelfQuery.filter = _selFilter.value; shelfQuery.page = 1; loadShelf(); });

const _inpSearch = document.getElementById("shelf-search");
if (_inpSearch) {
  let _searchTimer = null;
  _inpSearch.addEventListener("input", () => {
    clearTimeout(_searchTimer);
    _searchTimer = setTimeout(() => {
      shelfQuery.q = _inpSearch.value.trim();
      shelfQuery.page = 1;
      loadShelf();
    }, 300);
  });
}

loadShelf();


// ---------- 我的 ----------
function formatDuration(sec) {
  sec = Math.floor(sec || 0);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h > 0) return h + " 小时 " + m + " 分";
  return m + " 分钟";
}

function renderHeaderUser(u) {
  const chip = $("#header-user");
  if (!chip) return;
  if (u && (u.nick || u.name)) {
    $("#header-nick").textContent = u.nick || u.name;
    const img = $("#header-avatar");
    if (u.avatar) { img.src = u.avatar; img.style.display = ""; }
    else { img.style.display = "none"; }
    chip.classList.remove("hidden");
  } else {
    chip.classList.add("hidden");
  }
}

let _meLoaded = false;
async function loadMe(force) {
  if (_meLoaded && !force) return;
  const loading = $("#me-loading");
  const content = $("#me-content");
  if (loading) { loading.classList.remove("hidden"); loading.textContent = "加载中..."; }
  try {
    const u = await api("/api/user");
    renderHeaderUser(u);
    if (loading) loading.classList.add("hidden");
    if (content) content.classList.remove("hidden");
    $("#me-nick").textContent = u.nick || u.name || "微信读书用户";
    $("#me-uid").textContent = u.userVid ? ("UID: " + u.userVid) : "";
    $("#me-signature").textContent = u.signature || "";
    const av = $("#me-avatar");
    if (u.avatar) av.src = u.avatar;
    const s = u.stats || {};
    $("#stat-books").textContent = (s.total_books == null) ? "-" : s.total_books;
    $("#stat-reading").textContent = (s.reading_count == null) ? "-" : s.reading_count;
    $("#stat-finished").textContent = (s.finished_count == null) ? "-" : s.finished_count;
    $("#stat-time").textContent = formatDuration(s.total_seconds);
    const box = $("#me-recent");
    const list = u.recent || [];
    if (!list.length) {
      box.innerHTML = '<p class="me-empty">暂无记录</p>';
    } else {
      box.innerHTML = list.map((b) => {
        let prog = b.progress || 0;
        if (prog <= 1) prog = prog * 100;
        prog = Math.round(prog);
        return '<div class="me-book" data-bookid="' + escapeHtml(b.bookId || "") + '">'
          + '<img class="me-book-cover" src="' + escapeHtml(b.cover || "") + '" alt="">'
          + '<div class="me-book-info">'
          + '<div class="me-book-title">' + escapeHtml(b.title || "") + '</div>'
          + '<div class="me-book-author">' + escapeHtml(b.author || "") + '</div>'
          + '<div class="me-book-meta">阅读 ' + formatDuration(b.readingTime) + ' · 进度 ' + prog + '%</div>'
          + '</div></div>';
      }).join("");
      bindIntro(box, ".me-book[data-bookid]", "bookid", "right");
    }
    _meLoaded = true;
  } catch (e) {
    if (loading) loading.textContent = "加载失败：" + (e.message || e);
    renderHeaderUser(null);
  }
}

loadMe();


// ---------- 传书 ----------
function fmtSize(n) {
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / 1024 / 1024).toFixed(1) + " MB";
}

async function loadOutputs() {
  const list = $("#outputs-list");
  if (!list) return;
  list.innerHTML = "<div class='shelf-empty'>加载中...</div>";
  try {
    const q = new URLSearchParams(outputsQuery).toString();
    const data = await api("/api/outputs?" + q);
    list.innerHTML = "";
    if (!data.items.length) {
      list.innerHTML = "<div class='shelf-empty'>output 目录暂无文件</div>";
      return;
    }
    data.items.forEach((r) => {
      const item = document.createElement("div");
      item.className = "me-book file-book";
      const ext = (r.name.split(".").pop() || "").toLowerCase();
      const date = r.mtime ? new Date(r.mtime * 1000).toLocaleString("zh-CN") : "";
      item.innerHTML =
        '<div class="file-cover"><div class="file-ext">' + escapeHtml(ext) + '</div></div>' +
        '<div class="me-book-info">' +
        '<div class="me-book-title">' + escapeHtml(r.name) + '</div>' +
        '<div class="me-book-meta">' + fmtSize(r.size) + " · " + date + '</div>' +
        '</div>' +
        '<button data-name="' + escapeHtml(r.name) + '" class="danger btn-del-out">删除</button>';
      list.appendChild(item);

      // 异步匹配微信读书
      api("/api/match?name=" + encodeURIComponent(r.name)).then((m) => {
        if (!m || !m.matched) return;
        item.dataset.bookid = m.bookId;
        const box = item.querySelector(".file-cover");
        if (box && m.cover) {
          box.innerHTML = '<img class="file-cover-img" src="' + escapeHtml(m.cover) + '" alt="">';
        }
        if (m.intro) {
          _introCache[m.bookId] = {
            bookId: m.bookId,
            title: m.title || "",
            intro: m.intro,
            rating: m.rating || 0,
          };
        }
        item.addEventListener("mouseenter", () => showIntro(item, m.bookId, "right"));
        item.addEventListener("mouseleave", hideIntro);
      }).catch(() => {});
    });
    $$(".btn-del-out").forEach((b) => {
      b.addEventListener("click", async () => {
        if (!(await confirmBox("确认删除 " + b.dataset.name + "？"))) return;
        try {
          await api("/api/outputs/" + encodeURIComponent(b.dataset.name), { method: "DELETE", loading: true });
          toast("已删除");
          loadOutputs();
          loadShelf();
        } catch (e) { toast("删除失败：" + e.message); }
      });
    });
    renderPagerGeneric("outputs-pager", data, (p) => { outputsQuery.page = p; loadOutputs(); });
  } catch (e) {
    list.innerHTML = "<div class='shelf-empty'>加载失败：" + escapeHtml(e.message) + "</div>";
  }
}

async function doUpload(fileList) {
  if (!fileList || !fileList.length) return;
  const fd = new FormData();
  for (const f of fileList) fd.append("files", f, f.name);
  toast("上传中...（" + fileList.length + " 个文件）");
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json()).detail || detail; } catch (e) {}
      throw new Error(detail);
    }
    const d = await r.json();
    let msg = "上传成功 " + d.ok.length + " 本";
    if (d.skipped.length) msg += "，跳过 " + d.skipped.length;
    if (d.failed.length) msg += "，失败 " + d.failed.length;
    toast(msg);
    loadOutputs();
    loadShelf();
  } catch (e) {
    toast("上传失败：" + e.message);
  }
}

(function initUpload() {
  const zone = document.getElementById("upload-zone");
  const inp = document.getElementById("upload-input");
  if (!zone || !inp) return;
  zone.addEventListener("click", () => inp.click());
  inp.addEventListener("change", () => { doUpload(inp.files); inp.value = ""; });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer && e.dataTransfer.files) doUpload(e.dataTransfer.files);
  });
  const btn = document.getElementById("btn-refresh-outputs");
  if (btn) btn.addEventListener("click", loadOutputs);
})();


// ---------- 简介浮层 ----------
let _introPop = null;
let _introTimer = null;
let _introCache = {};

function ensureIntroPop() {
  if (_introPop) return _introPop;
  _introPop = document.createElement("div");
  _introPop.className = "intro-pop";
  document.body.appendChild(_introPop);
  return _introPop;
}

async function showIntro(anchor, bookId, mode) {
  const pop = ensureIntroPop();
  let data = _introCache[bookId];
  if (!data) {
    pop.innerHTML = '<div class="intro-text">加载中...</div>';
    positionIntro(pop, anchor, mode);
    pop.classList.add("show");
    try {
      data = await api("/api/book/" + encodeURIComponent(bookId) + "/intro");
      _introCache[bookId] = data;
    } catch (e) {
      pop.innerHTML = '<div class="intro-text">简介加载失败</div>';
      return;
    }
  }
  const rating = data.rating ? "★ " + (data.rating / 10).toFixed(1) : "";
  pop.innerHTML =
    '<div class="intro-title">' + escapeHtml(data.title || "") + '</div>' +
    (rating ? '<div class="intro-rating">' + rating + '</div>' : '') +
    '<div class="intro-text">' + escapeHtml(data.intro || "暂无简介") + '</div>';
  positionIntro(pop, anchor, mode);
  pop.classList.add("show");
}

function positionIntro(pop, anchor, mode) {
  const r = anchor.getBoundingClientRect();
  const pw = pop.offsetWidth || 320;
  const ph = pop.offsetHeight || 200;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (mode === "right") {
    let left = r.right + 12;
    if (left + pw > vw - 8) left = r.left - pw - 12;
    let top = r.top;
    if (top + ph > vh - 8) top = vh - ph - 8;
    pop.style.left = Math.max(8, left) + "px";
    pop.style.top = Math.max(8, top) + "px";
  } else {
    const left = Math.max(8, Math.min(r.left, vw - pw - 8));
    let top = r.bottom + 8;
    if (top + ph > vh - 8) top = r.top - ph - 8;
    pop.style.left = left + "px";
    pop.style.top = Math.max(8, top) + "px";
  }
}

function hideIntro() {
  if (_introPop) _introPop.classList.remove("show");
}

function showTip(anchor, text) {
  const pop = ensureIntroPop();
  pop.innerHTML = '<div class="intro-text" style="max-height:none">' + escapeHtml(text) + '</div>';
  positionIntro(pop, anchor, "below");
  pop.classList.add("show");
}

function bindIntro(container, selector, idAttr, mode) {
  container.querySelectorAll(selector).forEach((el) => {
    el.addEventListener("mouseenter", () => {
      clearTimeout(_introTimer);
      const bid = el.dataset[idAttr];
      if (!bid) return;
      _introTimer = setTimeout(() => showIntro(el, bid, mode), 350);
    });
    el.addEventListener("mouseleave", () => {
      clearTimeout(_introTimer);
      hideIntro();
    });
  });
}


// ---------- 通用分页器 ----------
function renderPagerGeneric(pagerId, data, onPage) {
  const pager = document.getElementById(pagerId);
  if (!pager) return;
  const total = data.total || 0;
  const pages = data.total_pages || 1;
  const page = data.page || 1;
  if (pages <= 1) { pager.innerHTML = "共 " + total + " 项"; return; }
  let html = "";
  html += "<button data-p=\"" + (page - 1) + "\" " + (page <= 1 ? "disabled" : "") + ">上一页</button>";
  html += "<span class=\"pager-info\">" + page + " / " + pages + "（共 " + total + " 项）</span>";
  html += "<button data-p=\"" + (page + 1) + "\" " + (page >= pages ? "disabled" : "") + ">下一页</button>";
  pager.innerHTML = html;
  pager.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      onPage(Number(btn.dataset.p));
    });
  });
}

let recordsQuery = { page: 1, page_size: 30 };
let outputsQuery = { page: 1, page_size: 30 };

function appendCancelBtn(wrap, bookId) {
  const btn = document.createElement("button");
  btn.className = "q-cancel";
  btn.textContent = "\u2715";
  btn.title = "取消下载";
  btn.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    try {
      await api("/api/download/cancel/" + encodeURIComponent(bookId), { method: "POST", loading: true });
      _localCancelled.add(bookId);
      // 乐观清空该卡片队列 UI
      const card = document.querySelector('#shelf-list .book-card[data-id="' + bookId + '"]');
      if (card) {
        card.classList.remove("q-pending", "q-downloading", "q-failed");
        const w = card.querySelector(".card-cover-wrap");
        if (w) w.querySelectorAll(".dl-ring, .q-badge, .q-cancel").forEach((e) => e.remove());
      }
      toast("已取消");
    } catch (e) { toast("取消失败：" + e.message); }
  });
  wrap.appendChild(btn);
}


// ---------- rate 悬浮提示 ----------
(function initRateTip() {
  const el = document.getElementById("rate-info");
  if (!el) return;
  el.style.cursor = "help";
  el.addEventListener("mouseenter", () => {
    if (el.dataset.tip) showTip(el, el.dataset.tip);
  });
  el.addEventListener("mouseleave", hideIntro);
})();


// ---------- 自动恢复未完成队列 ----------
// ---------- 未完成队列：提示条 + 开关分流 ----------
(async function checkRestore() {
  const banner = document.getElementById("restore-banner");
  const txt = document.getElementById("restore-text");
  const yes = document.getElementById("btn-restore-yes");
  const no = document.getElementById("btn-restore-no");
  if (!banner || !yes || !no) return;

  let _autoDone = false;

  async function refreshBanner() {
    try {
      const s = await api("/api/status");
      if (!(s.has_restore && s.download && !s.download.running)) {
        banner.classList.add("hidden");
        return;
      }
      let autoRestore = false;
      try {
        const cfg = await api("/api/config");
        autoRestore = !!cfg.auto_restore_enabled;
      } catch (e) {}
      if (autoRestore) {
        banner.classList.add("hidden");
        if (_autoDone) return;
        _autoDone = true;
        try {
          const r = await api("/api/download/resume_queue", { method: "POST" });
          _localCancelled.clear();
          toast("已自动继续 " + (r.count || 0) + " 本未完成下载");
          startDownloadSSE();
          refreshStatus();
        } catch (e) {}
        return;
      }
      txt.textContent = "上次有 " + (s.restore_count || 0) + " 本未完成下载";
      banner.classList.remove("hidden");
    } catch (e) {
      banner.classList.add("hidden");
    }
  }

  yes.addEventListener("click", async () => {
    try {
      const r = await api("/api/download/resume_queue", { method: "POST", loading: true });
      _localCancelled.clear();
      banner.classList.add("hidden");
      toast("已继续 " + (r.count || 0) + " 本");
      startDownloadSSE();
      refreshStatus();
    } catch (e) { toast("继续失败：" + e.message); }
  });

  no.addEventListener("click", async () => {
    if (!(await confirmBox("放弃未完成的下载队列？"))) return;
    try {
      await api("/api/download/cancel", { method: "POST", loading: true });
      banner.classList.add("hidden");
      toast("已放弃未完成队列");
      refreshStatus();
    } catch (e) { toast("取消失败：" + e.message); }
  });

  await refreshBanner();
  setInterval(refreshBanner, 5000);
})();


// 初始：默认「我的」，后台预热书架缓存
loadMe();
loadShelf();
