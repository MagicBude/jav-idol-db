/* jav-idol-db 站点逻辑 —— 纯前端，读取 window.JAV_DB（由 scripts/build_index.py 生成） */
(function () {
  "use strict";

  var DB = window.JAV_DB || { actresses: [] };

  // 图片路径相对于站点根（如 assets/img/桃乃木かな/avatar.jpg），直接使用
  function img(path) {
    return path || null;
  }

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

  // ---------------- 首页 ----------------
  function renderIndex() {
    var countEl = document.getElementById("count");
    if (countEl) {
      countEl.textContent =
        DB.counts ? DB.counts.actresses + " 位女优 · " + DB.counts.works + " 部作品"
                  : DB.actresses.length + " 位女优";
    }
    var aBox = document.getElementById("actresses");
    var wBox = document.getElementById("works");
    var empty = document.getElementById("empty");
    var q = document.getElementById("q");

    function draw(filter) {
      filter = (filter || "").trim().toLowerCase();
      var acts = DB.actresses.filter(function (a) {
        if (!filter) return true;
        if ((a.name || "").toLowerCase().indexOf(filter) >= 0) return true;
        return (a.aliases || []).some(function (x) { return x.toLowerCase().indexOf(filter) >= 0; });
      });
      var works = [];
      DB.actresses.forEach(function (a) {
        (a.works || []).forEach(function (w) {
          if (!filter) { works.push(w); return; }
          if ((w.code || "").toLowerCase().indexOf(filter) >= 0) { works.push(w); return; }
          if ((w.title || "").toLowerCase().indexOf(filter) >= 0) { works.push(w); return; }
          if ((a.name || "").toLowerCase().indexOf(filter) >= 0) { works.push(w); return; }
        });
      });

      aBox.innerHTML = "";
      acts.forEach(function (a) {
        var src = img(a.avatar);
        var card = el(
          '<a class="card" href="actress.html?name=' + encodeURIComponent(a.name) + '">' +
            '<div class="thumb' + (src ? '" style="background-image:url(\'' + esc(src) + '\')"' : '"') + '>' +
              (src ? "" : "无图") + '</div>' +
            '<div class="body"><div class="name">' + esc(a.name) + '</div>' +
            '<div class="sub">' + (a.work_count || 0) + ' 部</div></div></a>'
        );
        aBox.appendChild(card);
      });

      wBox.innerHTML = "";
      works.forEach(function (w) {
        var src = img(w.cover);
        var card = el(
          '<a class="card" href="work.html?code=' + encodeURIComponent(w.code) + '">' +
            '<div class="thumb' + (src ? '" style="background-image:url(\'' + esc(src) + '\')"' : '"') + '>' +
              (src ? "" : esc(w.code)) + '</div>' +
            '<div class="body"><div class="name">' + esc(w.code) + '</div>' +
            '<div class="sub">' + (w.title ? esc(w.title) : "（片名待抓取）") + '</div></div></a>'
        );
        wBox.appendChild(card);
      });

      empty.style.display = (acts.length + works.length === 0) ? "block" : "none";
    }

    draw("");
    if (q) q.addEventListener("input", function () { draw(q.value); });
  }

  // ---------------- 女优详情 ----------------
  function renderActress() {
    var name = getParam("name") || "";
    var a = DB.actresses.filter(function (x) { return x.name === name; })[0];
    var c = document.getElementById("content");
    if (!a) { c.innerHTML = '<div class="empty">未找到女优：' + esc(name) + '</div>'; return; }

    var src = img(a.avatar);
    var rows = "";
    if (a.aliases && a.aliases.length) rows += row("别名", a.aliases.join("、"));
    if (a.birthdate) rows += row("生日", a.birthdate);
    if (a.height) rows += row("身高", a.height + " cm");
    if (a.measurements) rows += row("三围", a.measurements);
    if (a.agency) rows += row("事务所", a.agency);
    rows += row("作品数", (a.work_count || 0) + " 部");

    var head =
      '<div class="detail-head">' +
        '<div class="poster' + (src ? '" style="background-image:url(\'' + esc(src) + '\')"' : '"') + '>' +
          (src ? "" : "无图") + '</div>' +
        '<div class="meta"><h1>' + esc(a.name) + '</h1>' + rows + '</div></div>';

    var grid = '<div class="section-title">作品</div><div class="grid wide">';
    (a.works || []).forEach(function (w) {
      var ws = img(w.cover);
      grid +=
        '<a class="card" href="work.html?code=' + encodeURIComponent(w.code) + '">' +
          '<div class="thumb' + (ws ? '" style="background-image:url(\'' + esc(ws) + '\')"' : '"') + '>' +
            (ws ? "" : esc(w.code)) + '</div>' +
          '<div class="body"><div class="name">' + esc(w.code) + '</div>' +
          '<div class="sub">' + (w.title ? esc(w.title) : "（片名待抓取）") + '</div></div></a>';
    });
    grid += "</div>";

    c.innerHTML = head + grid;
  }

  // ---------------- 作品详情 ----------------
  function renderWork() {
    var code = getParam("code") || "";
    var found = null, owner = null;
    DB.actresses.forEach(function (a) {
      (a.works || []).forEach(function (w) { if (w.code === code) { found = w; owner = a; } });
    });
    var c = document.getElementById("content");
    if (!found) { c.innerHTML = '<div class="empty">未找到作品：' + esc(code) + '</div>'; return; }

    var src = img(found.cover);
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

    var head =
      '<div class="detail-head">' +
        '<div class="poster' + (src ? '" style="background-image:url(\'' + esc(src) + '\')"' : '"') + '>' +
          (src ? "" : esc(found.code)) + '</div>' +
        '<div class="meta"><h1>' + esc(found.code) + '</h1>' + rows +
          (tags ? '<div style="margin-top:8px">' + tags + '</div>' : "") + '</div></div>';

    c.innerHTML = head;
  }

  function row(label, val) {
    return '<div class="row"><b>' + esc(label) + '：</b>' + esc(val) + '</div>';
  }

  // ---------------- 路由 ----------------
  var page = document.body.getAttribute("data-page");
  if (page === "index") renderIndex();
  else if (page === "actress") renderActress();
  else if (page === "work") renderWork();
})();
