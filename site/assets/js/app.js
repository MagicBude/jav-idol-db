/* ===================================================================
   jav-idol-db 站点逻辑
   纯前端，读取 window.JAV_DB（由 scripts/build_index.py 生成）
   零网络请求，file:// 可直接渲染
   =================================================================== */
(function () {
  "use strict";

  var DB = window.JAV_DB || { actresses: [], counts: {} };
  var PAGE_SIZE = 60;   // 首页作品默认展示数
  var worksShown  = PAGE_SIZE;

  /* ---- 工具 ---- */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function el(html) {
    var d = document.createElement("div");
    d.innerHTML = html.trim();
    return d.firstChild;
  }
  function getParam(name) {
    return new URLSearchParams(location.search).get(name);
  }

  /* ---- 女优卡片 ---- */
  function actressCard(a) {
    var src = a.avatar || null;
    var style = src ? ' style="background-image:url(\'' + esc(src) + '\')"' : '';
    return el(
      '<a class="card" href="actress.html?name=' + encodeURIComponent(a.name) + '">' +
        '<div class="thumb portrait"' + style + '>' +
          (src ? "" : esc(a.name)) + '</div>' +
        '<div class="body"><div class="name">' + esc(a.name) + '</div>' +
        '<div class="sub">' + (a.work_count || 0) + ' 部作品</div></div></a>'
    );
  }

  /* ---- 作品卡片 ---- */
  function workCard(w, ownerName) {
    var src = w.cover || null;
    var style = src ? ' style="background-image:url(\'' + esc(src) + '\')"' : '';
    return el(
      '<a class="card" href="work.html?code=' + encodeURIComponent(w.code) + '">' +
        '<div class="thumb"' + style + '>' +
          (src ? "" : esc(w.code)) + '</div>' +
        '<div class="body"><div class="name">' + esc(w.code) + '</div>' +
        '<div class="sub">' + (w.title ? esc(w.title) : "（片名待抓取）") + '</div></div></a>'
    );
  }

  /* ---- 聚合全部作品（附带 ownerName 用于搜索匹配） ---- */
  function allWorks() {
    var out = [];
    DB.actresses.forEach(function (a) {
      (a.works || []).forEach(function (w) {
        out.push({ w: w, owner: a.name });
      });
    });
    return out;
  }

  /* =================================================================
     首页
     ================================================================= */
  function renderIndex() {
    var totalActresses = (DB.counts && DB.counts.actresses) || DB.actresses.length;
    var totalWorks = (DB.counts && DB.counts.works) || 0;

    /* 统计数字 */
    setText("stat-actresses", totalActresses);
    setText("stat-works", totalWorks);

    var aBox = document.getElementById("actresses");
    var wBox = document.getElementById("works");
    var empty = document.getElementById("empty");
    var actressCountEl = document.getElementById("actress-count");
    var workCountEl = document.getElementById("work-count");
    var q = document.getElementById("q");
    var loadMoreBtn = document.getElementById("load-more");
    var allW = allWorks();

    function draw(filter) {
      filter = (filter || "").trim().toLowerCase();
      var isFiltering = !!filter;

      /* ---- 过滤女优 ---- */
      var acts = DB.actresses.filter(function (a) {
        if (!filter) return true;
        if ((a.name || "").toLowerCase().indexOf(filter) >= 0) return true;
        return (a.aliases || []).some(function (x) {
          return x.toLowerCase().indexOf(filter) >= 0;
        });
      });

      /* ---- 过滤作品 ---- */
      var works = [];
      allW.forEach(function (item) {
        if (!filter) { works.push(item.w); return; }
        var w = item.w;
        if ((w.code || "").toLowerCase().indexOf(filter) >= 0) { works.push(w); return; }
        if ((w.title || "").toLowerCase().indexOf(filter) >= 0) { works.push(w); return; }
        if ((item.owner || "").toLowerCase().indexOf(filter) >= 0) { works.push(w); return; }
      });

      /* ---- 渲染女优 ---- */
      aBox.innerHTML = "";
      acts.forEach(function (a) { aBox.appendChild(actressCard(a)); });

      /* ---- 渲染作品（搜索时全量，默认分页） ---- */
      var toShow = isFiltering ? works : works.slice(0, worksShown);
      wBox.innerHTML = "";
      toShow.forEach(function (w) { wBox.appendChild(workCard(w)); });

      /* ---- 计数标签 ---- */
      if (actressCountEl)
        actressCountEl.textContent = acts.length + " 位";
      if (workCountEl) {
        if (isFiltering) {
          workCountEl.textContent = works.length + " 部";
        } else {
          workCountEl.textContent = Math.min(worksShown, works.length) + " / " + works.length + " 部";
        }
      }

      /* ---- 加载更多按钮 ---- */
      if (loadMoreBtn) {
        loadMoreBtn.style.display = (!isFiltering && works.length > worksShown) ? "" : "none";
      }

      /* ---- 空状态 ---- */
      empty.style.display = (acts.length + works.length === 0) ? "block" : "none";
    }

    /* ---- 初始渲染 ---- */
    draw("");

    /* ---- 搜索框 ---- */
    if (q) {
      q.addEventListener("input", function () {
        if (!q.value.trim()) worksShown = PAGE_SIZE; /* 清空搜索 → 重置分页 */
        draw(q.value);
      });
    }

    /* ---- 加载更多 ---- */
    if (loadMoreBtn) {
      loadMoreBtn.addEventListener("click", function () {
        worksShown += PAGE_SIZE;
        draw(q ? q.value : "");
        /* 滚到新内容顶部 */
        var cards = wBox.querySelectorAll(".card");
        if (cards.length > worksShown - PAGE_SIZE) {
          cards[worksShown - PAGE_SIZE].scrollIntoView({ behavior: "smooth", block: "center" });
        }
      });
    }
  }

  /* =================================================================
     女优详情
     ================================================================= */
  function renderActress() {
    var name = getParam("name") || "";
    var a = DB.actresses.filter(function (x) { return x.name === name; })[0];
    var c = document.getElementById("content");
    if (!a) { c.innerHTML = '<div class="empty">未找到女优：' + esc(name) + '</div>'; return; }

    var src = a.avatar || null;
    var style = src ? ' style="background-image:url(\'' + esc(src) + '\')"' : '';
    var rows = "";
    if (a.aliases && a.aliases.length) rows += row("别名", a.aliases.join("、"));
    if (a.birthdate) rows += row("生日", a.birthdate);
    if (a.height) rows += row("身高", a.height + " cm");
    if (a.measurements) rows += row("三围", a.measurements);
    if (a.agency) rows += row("事务所", a.agency);
    rows += row("作品数", (a.work_count || 0) + " 部");

    var head =
      '<div class="detail-head">' +
        '<div class="poster"' + style + '>' + (src ? "" : esc(a.name)) + '</div>' +
        '<div class="meta"><h1>' + esc(a.name) + '</h1>' + rows + '</div></div>';

    var grid = '<div class="section" style="margin-top:32px">' +
      '<div class="section-header"><h2 class="section-title">作品</h2>' +
      '<span class="section-count">' + (a.works || []).length + ' 部</span></div>' +
      '<div class="grid work-grid">';
    (a.works || []).forEach(function (w) {
      grid += workCardHTML(w);
    });
    grid += "</div></div>";

    c.innerHTML = head + grid;
  }

  /* =================================================================
     作品详情
     ================================================================= */
  function renderWork() {
    var code = getParam("code") || "";
    var found = null, owner = null;
    DB.actresses.forEach(function (a) {
      (a.works || []).forEach(function (w) { if (w.code === code) { found = w; owner = a; } });
    });
    var c = document.getElementById("content");
    if (!found) { c.innerHTML = '<div class="empty">未找到作品：' + esc(code) + '</div>'; return; }

    var src = found.cover || null;
    var style = src ? ' style="background-image:url(\'' + esc(src) + '\')"' : '';
    var rows = "";
    rows += row("片名", found.title || "（待抓取）");
    if (found.date) rows += row("发行日", found.date);
    if (owner) rows += '<div class="row"><b>女优：</b><a href="actress.html?name=' +
      encodeURIComponent(owner.name) + '">' + esc(owner.name) + '</a></div>';
    if (found.series) rows += row("系列", found.series);
    if (found.maker) rows += row("片商", found.maker);
    if (found.segments) rows += row("分卷", found.segments + " 个");

    var tags = "";
    (found.labels || []).concat(found.tags || []).forEach(function (t) {
      if (t) tags += '<span class="tag">' + esc(t) + "</span>";
    });

    c.innerHTML =
      '<div class="detail-head">' +
        '<div class="poster"' + style + '>' + (src ? "" : esc(found.code)) + '</div>' +
        '<div class="meta"><h1>' + esc(found.code) + '</h1>' + rows +
          (tags ? '<div style="margin-top:8px">' + tags + '</div>' : "") + '</div></div>';
  }

  /* ---- 辅助：生成作品卡片 HTML 字符串（详情页用） ---- */
  function workCardHTML(w) {
    var ws = w.cover || null;
    var style = ws ? ' style="background-image:url(\'' + esc(ws) + '\')"' : '';
    return '<a class="card" href="work.html?code=' + encodeURIComponent(w.code) + '">' +
      '<div class="thumb"' + style + '>' + (ws ? "" : esc(w.code)) + '</div>' +
      '<div class="body"><div class="name">' + esc(w.code) + '</div>' +
      '<div class="sub">' + (w.title ? esc(w.title) : "（片名待抓取）") + '</div></div></a>';
  }

  function row(label, val) {
    return '<div class="row"><b>' + esc(label) + '：</b>' + esc(val) + '</div>';
  }

  function setText(id, text) {
    var e = document.getElementById(id);
    if (e) e.textContent = text;
  }

  /* =================================================================
     路由
     ================================================================= */
  var page = document.body.getAttribute("data-page");
  if (page === "index") renderIndex();
  else if (page === "actress") renderActress();
  else if (page === "work") renderWork();
})();
