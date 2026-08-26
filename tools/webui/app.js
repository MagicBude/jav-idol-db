// JAV 查询台 · 前端逻辑（原生 JS，无框架）
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  let mode = "code";

  // ---- 源状态条 ----
  async function loadSources() {
    try {
      const r = await fetch("/api/sources");
      const j = await r.json();
      const box = $("#sources");
      box.innerHTML = "";
      for (const [name, desc] of Object.entries(j.sources || {})) {
        const local = name === "codeav";
        const chip = document.createElement("span");
        chip.className = "chip " + (local ? "local" : "remote");
        chip.title = desc;
        chip.innerHTML = `<span class="dot"></span><b>${name}</b>`;
        box.appendChild(chip);
      }
    } catch (e) { /* 忽略 */ }
  }

  // ---- 渲染辅助 ----
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }
  function cover(src, cls) {
    if (!src) return `<div class="cover broken ${cls || ""}">无封面</div>`;
    return `<img class="cover ${cls || ""}" src="${esc(src)}" alt="cover" onerror="imgFail(this)" />`;
  }
  // 封面加载失败时的兜底（避免在 onerror 内联里写带引号 HTML 引发语法错误）
  window.imgFail = function (el) {
    const d = document.createElement("div");
    d.className = "cover broken" + (el.className ? " " + el.className.replace("cover", "").trim() : "");
    d.textContent = "封面不可用";
    el.replaceWith(d);
  };
  function tags(arr) {
    if (!arr || !arr.length) return "";
    return `<div class="tags">${arr.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>`;
  }

  function showJSON(obj) {
    $("#result").innerHTML = `<pre class="json">${esc(JSON.stringify(obj, null, 2))}</pre>`;
  }
  function showError(msg) {
    $("#result").innerHTML = `<div class="err">${esc(msg)}</div>`;
  }
  function showLoader() {
    $("#result").innerHTML = `<div class="loader">查询中…</div>`;
  }

  // ---- 渲染：作品（多源聚合对比） ----
  // 核心卖点：一次查 4 站，合并结果 + 高亮各源差异，这是单站 codeav 做不到的。
  function fieldVal(src, f) {
    const v = src[f];
    if (f === "actresses") return Array.isArray(v) && v.length ? v.join("、") : (src.actress || "");
    if (Array.isArray(v)) return v.join("、");
    return v == null ? "" : String(v);
  }

  function renderCompare(d) {
    const per = d.sources || {};
    const names = Object.keys(per);
    const okNames = names.filter((n) => per[n].ok && per[n].data);
    const failNames = names.filter((n) => !per[n].ok);

    // 顶部：各源状态卡（命中显示封面缩略图，未命中显示原因）
    const cards = names.map((n) => {
      const s = per[n];
      if (s.ok && s.data) {
        return `<div class="srccard ok"><div class="srch">${esc(n)} <span class="tick">✓</span></div>${cover(s.data.cover, "thumb")}</div>`;
      }
      const err = s.error || "";
      const reason = err.includes("不可达") ? "需本机宽网络" : err.includes("超时") ? "超时" : (err || "未命中");
      return `<div class="srccard fail"><div class="srch">${esc(n)} <span class="cross">✗</span></div><div class="srcreason">${esc(reason)}</div></div>`;
    }).join("");

    // 合并后的主卡（取最佳值）
    const a = d.actress || "";
    const az = d.actress_zh ? `<span class="actress-zh">（${esc(d.actress_zh)}）</span>` : "";
    const hero = `
      <div class="card">
        ${cover(d.cover)}
        <div class="meta">
          <h2>${esc(d.title || d.code)}</h2>
          <div class="kv">
            <div class="k">番号</div><div class="v">${esc(d.code)}</div>
            <div class="k">女优</div><div class="v">${esc(a)}${az}</div>
            <div class="k">日期</div><div class="v">${esc(d.date)}</div>
            <div class="k">厂商</div><div class="v">${esc(d.maker)}</div>
            <div class="k">厂牌</div><div class="v">${esc(d.label)}</div>
            <div class="k">系列</div><div class="v">${esc(d.series)}</div>
            <div class="k">时长</div><div class="v">${d.duration ? d.duration + " 分" : ""}</div>
            <div class="k">评分</div><div class="v">${d.rating != null ? d.rating + (d.rating_count ? `（${d.rating_count} 票）` : "") : ""}</div>
          </div>
          ${tags(d.tags)}
          <div class="srcstat">命中源：${okNames.map((n) => `<span class="ok">${esc(n)}</span>`).join(" ")}${failNames.length ? " · 未命中：" + failNames.map((n) => `<span class="fail">${esc(n)}</span>`).join(" ") : ""}</div>
        </div>
      </div>`;

    // 各源差异对照表
    const fields = [["title", "标题"], ["actresses", "女优"], ["maker", "厂商"], ["date", "日期"], ["series", "系列"]];
    let diffTable = "";
    if (okNames.length > 1) {
      const rows = fields.map(([f, label]) => {
        const vals = okNames.map((n) => fieldVal(per[n].data, f));
        const distinct = new Set(vals.map((v) => JSON.stringify(v))).size;
        const conflict = distinct > 1;
        return `<tr class="${conflict ? "conflict" : ""}"><td class="fld">${label}</td>${vals.map((v) => `<td>${esc(v) || '<span class="muted">—</span>'}</td>`).join("")}</tr>`;
      }).join("");
      diffTable = `
        <div class="section-title">各源对照（<span class="conflict-mark">红框=各源不一致</span>）</div>
        <table class="diff">
          <tr><th class="fld">字段</th>${okNames.map((n) => `<th>${esc(n)}</th>`).join("")}</tr>
          ${rows}
        </table>`;
    } else if (okNames.length === 1) {
      diffTable = `<div class="hint">仅 ${esc(okNames[0])} 命中，无其他源可对照（本机跑时 javbus/javdb/fanza 会一并返回）。</div>`;
    }

    const unreachableNote = failNames.length
      ? `<div class="hint">提示：${failNames.join("、")} 在当前环境不可达（沙箱仅放行 codeav）。在你本机用 Playwright 跑时它们会实际抓取并参与合并。</div>`
      : "";

    $("#result").innerHTML = hero + `<div class="srccards">${cards}</div>` + diffTable + unreachableNote;
  }

  // ---- 渲染：女优 ----
  function renderActress(d) {
    const az = d.name_zh ? ` <span class="actress-zh">（${esc(d.name_zh)}）</span>` : "";
    const av = d.avatar
      ? `<img src="${esc(d.avatar)}" alt="avatar" onerror="this.style.visibility='hidden'" />`
      : `<div style="width:96px;height:96px;border-radius:50%;background:var(--bg3);display:grid;place-items:center;color:var(--txt2)">无头像</div>`;
    const items = (d.works || []).map((w) => `
      <div class="gitem" data-code="${esc(w.code)}">
        ${cover(w.cover)}
        <div class="gmeta"><div class="code">${esc(w.code)}</div>
        <div class="title">${esc(w.title)}</div></div>
      </div>`).join("");
    $("#result").innerHTML = `
      <div class="actress-head">${av}
        <div><h2>${esc(d.name)}${az}</h2>
        <div class="cnt">${d.work_count || 0} 部作品 · <a class="link" href="${esc(d.url)}" target="_blank" rel="noopener">来源</a></div></div>
      </div>
      <div class="grid">${items}</div>`;
  }

  // ---- 渲染：搜索 ----
  function renderSearch(d) {
    const movies = (d.movies || []).map((w) => `
      <div class="gitem" data-code="${esc(w.code)}">
        ${cover(w.cover)}
        <div class="gmeta"><div class="code">${esc(w.code)}</div>
        <div class="title">${esc(w.title)}</div></div>
      </div>`).join("");
    const actors = (d.actresses || []).map((a) => `
      <div class="gitem" data-actress="${esc(a.name)}" data-slug="${esc(a.slug)}">
        ${cover(a.avatar)}
        <div class="gmeta"><div class="code">${esc(a.name)}</div>
        <div class="title">${a.work_count ? a.work_count + " 部" : ""}</div></div>
      </div>`).join("");
    $("#result").innerHTML = `
      ${actors ? `<div class="section-title">女优（${d.actresses.length}）</div><div class="grid">${actors}</div>` : ""}
      <div class="section-title">作品（${d.movies ? d.movies.length : 0}）</div>
      <div class="grid">${movies || '<div class="hint">无结果</div>'}</div>`;
  }

  // ---- 事件 ----
  async function run() {
    const q = $("#q").value.trim();
    if (!q) { showError("请输入查询内容"); return; }
    const src = $("#source").value;
    const asJson = $("#json").checked;
    showLoader();
    try {
      let url, data;
      if (mode === "code") url = `/api/code?code=${encodeURIComponent(q)}&source=${encodeURIComponent(src)}`;
      else if (mode === "actress") url = `/api/actress?name=${encodeURIComponent(q)}`;
      else url = `/api/search?q=${encodeURIComponent(q)}&source=${encodeURIComponent(src)}`;
      const r = await fetch(url);
      data = await r.json();
      if (asJson) { showJSON(data); return; }
      if (!data.ok) { showError(data.error || "未命中"); return; }
      if (mode === "code") renderCompare(data);
      else if (mode === "actress") renderActress(data);
      else renderSearch(data);
    } catch (e) {
      showError("请求失败：" + e.message);
    }
  }

  // 点击网格项 → 进入对应详情
  $("#result").addEventListener("click", (e) => {
    const g = e.target.closest(".gitem");
    if (!g) return;
    if (g.dataset.code) { mode = "code"; $("#q").value = g.dataset.code; run(); }
    else if (g.dataset.actress) { mode = "actress"; $("#q").value = g.dataset.actress; run(); }
  });

  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      mode = t.dataset.mode;
      const ph = mode === "actress" ? "输入女优名，如 白桃はな"
        : mode === "search" ? "输入关键词，如 桃乃木かな"
        : "输入番号，如 STARS-145";
      $("#q").placeholder = ph;
      if (mode === "actress") $("#source").value = "codeav";
    });
  });
  $("#go").addEventListener("click", run);
  $("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });

  loadSources();
})();
