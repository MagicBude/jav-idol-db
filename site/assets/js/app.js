/* ===================================================================
   jav-idol-db 站点逻辑（中文 JAV 资料库 单页 SPA）
   - 读取 window.JAV_DB（scripts/build_index.py 生成），含 zh 中文别名层
   - hash 路由：#/ 首页 | #/a/<女优> | #/w/<番号> |
                #/t/<标签> | #/m/<片商> | #/s/<系列> | #/q/<搜索>
   - 标签 / 片商 / 系列 / 女优 全部可点，跳转筛选视图
   - 纯前端，file:// 双击或 GitHub Pages 均可运行
   =================================================================== */
(function () {
  "use strict";

  var DB = window.JAV_DB || { actresses: [], counts: {} };
  var ZH = (DB.zh || {});
  var ACTRESS_ZH = ZH.actress_zh || {};   // 日文女优名 -> 中文名
  var TAG_ZH = ZH.tag_zh || {};            // 日文标签 -> 中文
  // 反向映射：中文 -> 日文（用于中文搜索命中）
  var ZH_TO_JP_ACTRESS = {};
  Object.keys(ACTRESS_ZH).forEach(function (jp) { ZH_TO_JP_ACTRESS[ACTRESS_ZH[jp]] = jp; });
  var ZH_TO_JP_TAG = {};
  Object.keys(TAG_ZH).forEach(function (jp) { ZH_TO_JP_TAG[TAG_ZH[jp]] = jp; });

  // 女优显示名：有中文则显示「中文（日文）」
  function actressName(jp) {
    var zh = ACTRESS_ZH[jp];
    return zh ? (zh + "（" + jp + "）") : jp;
  }
  // 标签显示名：有中文则显示中文
  function tagName(jp) {
    return TAG_ZH[jp] || jp;
  }

  // 中文感知搜索：q 已 lowercased；命中 番号/片名/女优(中或日)/厂牌/系列/标签(中或日)
  function workMatchesQuery(r, q) {
    if (!q) return true;
    var w = r.w;
    if ((w.code || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.title || "").toLowerCase().indexOf(q) >= 0) return true;
    var o = r.owner || "";
    if (o.toLowerCase().indexOf(q) >= 0) return true;
    if ((ACTRESS_ZH[o] || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.maker || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.label || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.series || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.tags || []).some(function (t) {
      return t.toLowerCase().indexOf(q) >= 0 || (TAG_ZH[t] || "").toLowerCase().indexOf(q) >= 0;
    })) return true;
    return false;
  }

  /* ---- 扁平化作品（带上归属女优）---- */
  var WORKS = [];          // [{w, owner, ownerAvatar}]
  var BY_CODE = {};        // code -> {w, owner}
  DB.actresses.forEach(function (a) {
    (a.works || []).forEach(function (w) {
      var rec = { w: w, owner: a.name, ownerAvatar: a.avatar };
      WORKS.push(rec);
      BY_CODE[w.code] = rec;
    });
  });

  /* ---- 工具 ---- */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  /** 生成 <img> 封面标签（替代 background-image，可加 referrerpolicy / onerror） */
  function imgTag(url, alt, cls) {
    if (!url) return "";
    return '<img src="' + esc(url) + '" alt="' + esc(alt || "") + '" ' +
      'loading="lazy" referrerpolicy="no-referrer" ' +
      'onerror="this.style.display=\'none\'" ' +
      (cls ? 'class="' + cls + '"' : '') + '>';
  }
  function $(id) { return document.getElementById(id); }

  /* 解码 hash 段（支持中文/特殊字符）*/
  function dec(s) { try { return decodeURIComponent(s); } catch (e) { return s; } }
  function enc(s) { return encodeURIComponent(s); }

  /* ---- 排序 ---- */
  var SORTERS = {
    date_desc: function (a, b) { return (b.w.date || "").localeCompare(a.w.date || ""); },
    date_asc:  function (a, b) { return (a.w.date || "").localeCompare(b.w.date || ""); },
    rating_desc: function (a, b) { return (b.w.rating || 0) - (a.w.rating || 0); },
    duration_desc: function (a, b) { return (b.w.duration || 0) - (a.w.duration || 0); },
    code_asc: function (a, b) { return (a.w.code || "").localeCompare(b.w.code || ""); }
  };
  function sortControls(current) {
    var opts = [
      ["date_desc", "最新发行"], ["date_asc", "最早发行"],
      ["rating_desc", "评分最高"], ["duration_desc", "时长最长"], ["code_asc", "番号排序"]
    ];
    var html = '<div class="sortbar"><label>排序</label><select id="sortsel">';
    opts.forEach(function (o) {
      html += '<option value="' + o[0] + '"' + (o[0] === current ? " selected" : "") + ">" + o[1] + "</option>";
    });
    html += "</select></div>";
    return html;
  }

  /* ---- 作品卡片 ---- */
  function workCard(rec) {
    var w = rec.w;
    var rating = w.rating ? '<span class="badge">★ ' + w.rating + "</span>" : "";
    var title = w.title ? esc(w.title) : "（片名待抓取）";
    return (
      '<a class="card" href="#/w/' + enc(w.code) + '">' +
        '<div class="thumb">' +
          imgTag(w.cover, w.code, "cover-img") +
          (w.cover ? "" : '<span class="ph">' + esc(w.code) + "</span>") +
          rating +
        "</div>" +
        '<div class="body">' +
          '<div class="name">' + esc(w.code) + "</div>" +
          '<div class="sub">' + title + "</div>" +
          '<div class="meta">' + (w.date || "") + (rec.owner ? " · " + esc(actressName(rec.owner)) : "") + "</div>" +
        "</div>" +
      "</a>"
    );
  }

  /* ---- 女优卡片 ---- */
  function actressCard(a) {
    return (
      '<a class="card actress" href="#/a/' + enc(a.name) + '">' +
        '<div class="thumb portrait">' +
          imgTag(a.avatar, a.name, "cover-img") +
          (a.avatar ? "" : '<span class="ph">' + esc(a.name) + "</span>") +
        "</div>" +
        '<div class="body"><div class="name">' + esc(actressName(a.name)) + "</div>" +
        '<div class="sub">' + (a.work_count || 0) + " 部作品</div></div></a>"
    );
  }

  /* ---- 可点击的标签 / 片商 / 系列 chips ---- */
  function chip(type, val) {
    if (!val) return "";
    var route = { t: "#/t/", m: "#/m/", s: "#/s/" }[type];
    var label = (type === "t") ? tagName(val) : val;
    return '<a class="chip" href="' + route + enc(val) + '">' + esc(label) + "</a>";
  }
  function chips(type, arr) {
    if (!arr || !arr.length) return "";
    return arr.map(function (v) { return chip(type, v); }).join("");
  }

  /* ---- 网格容器 ---- */
  function gridHtml(recs) {
    if (!recs.length) return '<div class="empty">没有匹配的作品。</div>';
    return '<div class="grid">' + recs.map(workCard).join("") + "</div>";
  }

  /* =================================================================
     视图：首页
     ================================================================= */
  function viewHome() {
    var acts = DB.actresses;
    var recent = WORKS.slice().sort(SORTERS.date_desc);
    // 取最新 60 部
    var latest = recent.slice(0, 60);

    // 热门标签（按出现次数）
    var tagCount = {};
    WORKS.forEach(function (r) {
      (r.w.tags || []).forEach(function (t) { tagCount[t] = (tagCount[t] || 0) + 1; });
    });
    var hotTags = Object.keys(tagCount).sort(function (a, b) { return tagCount[b] - tagCount[a]; })
      .slice(0, 24);

    return (
      '<section class="hero">' +
        '<h1>JAV 中文资料库</h1>' +
        '<p class="lead">' + (DB.counts.actresses || acts.length) + " 位女优 · " +
          (DB.counts.works || WORKS.length) + " 部作品 · 支持中文 / 日文 / 英文检索，标签 / 片商 / 系列 一键筛选</p>" +
      "</section>" +

      '<section class="block">' +
        '<div class="block-head"><h2>女优</h2><span class="muted">' + acts.length + " 位</span></div>" +
        '<div class="grid actress-grid">' + acts.map(actressCard).join("") + "</div>" +
      "</section>" +

      (hotTags.length ? '<section class="block">' +
        '<div class="block-head"><h2>热门标签</h2></div>' +
        '<div class="chipcloud">' + hotTags.map(function (t) { return chip("t", t); }).join("") + "</div>" +
      "</section>" : "") +

      '<section class="block">' +
        '<div class="block-head"><h2>最新发行</h2>' +
          '<a class="more" href="#/q/">查看全部 →</a></div>' +
        gridHtml(latest) +
      "</section>"
    );
  }

  /* =================================================================
     视图：女优详情
     ================================================================= */
  function viewActress(name) {
    var a = null;
    DB.actresses.forEach(function (x) { if (x.name === name) a = x; });
    if (!a) return '<div class="empty">未找到女优：' + esc(name) + "</div>";
    var recs = (a.works || []).map(function (w) { return BY_CODE[w.code] || { w: w, owner: a.name }; });
    return (
      '<div class="crumb"><a href="#/">首页</a> / 女优 / <b>' + esc(a.name) + "</b></div>" +
      '<div class="profile">' +
        '<div class="avatar">' + imgTag(a.avatar, a.name) + (a.avatar ? "" : esc(actressName(a.name))) + "</div>" +
        "<div class=\"pinfo\">" +
          "<h1>" + esc(actressName(a.name)) + "</h1>" +
          (a.aliases && a.aliases.length ? '<div class="row">别名：' + a.aliases.map(esc).join("、") + "</div>" : "") +
          (a.birthdate ? '<div class="row">生日：' + esc(a.birthdate) + "</div>" : "") +
          (a.height ? '<div class="row">身高：' + esc(a.height) + " cm</div>" : "") +
          (a.measurements ? '<div class="row">三围：' + esc(a.measurements) + "</div>" : "") +
          (a.agency ? '<div class="row">事务所：' + esc(a.agency) + "</div>" : "") +
          '<div class="row">作品数：' + (a.work_count || 0) + " 部</div>" +
        "</div>" +
      "</div>" +
      '<div class="block-head"><h2>作品</h2><span class="muted">' + recs.length + " 部</span></div>" +
      sortControls("date_desc") +
      '<div id="gridwrap">' + gridHtml(recs.sort(SORTERS.date_desc)) + "</div>"
    );
  }

  /* =================================================================
     视图：作品详情
     ================================================================= */
  function viewWork(code) {
    var rec = BY_CODE[code];
    if (!rec) return '<div class="empty">未找到作品：' + esc(code) + "</div>";
    var w = rec.w;
    var rows = "";
    if (w.date) rows += row("发行日", w.date);
    if (rec.owner) rows += '<div class="row"><b>女优</b>：<a href="#/a/' + enc(rec.owner) + '">' + esc(actressName(rec.owner)) + "</a></div>";
    if (w.maker) rows += '<div class="row"><b>片商</b>：' + chip("m", w.maker) + "</div>";
    if (w.label) rows += '<div class="row"><b>厂牌</b>：' + chip("m", w.label) + "</div>";
    if (w.series) rows += '<div class="row"><b>系列</b>：' + chip("s", w.series) + "</div>";
    if (w.duration) rows += row("时长", w.duration + " 分钟");
    if (w.director) rows += row("导演", w.director);
    if (w.rating) rows += row("评分", "★ " + w.rating + (w.rating_count ? "（" + w.rating_count + " 评价）" : ""));

    var tagHtml = chips("t", (w.labels || []).concat(w.tags || []));

    // 外部链接
    var ext = "";
    if (w.external_links) {
      var links = w.external_links;
      if (typeof links === "string") links = { "链接": links };
      Object.keys(links).forEach(function (k) {
        if (links[k]) ext += '<a class="extbtn" href="' + esc(links[k]) + '" target="_blank" rel="noopener">' + esc(k) + " ↗</a>";
      });
    }
    if (w.trailer) ext += '<a class="extbtn" href="' + esc(w.trailer) + '" target="_blank" rel="noopener">观看预告片 ▶</a>';

    return (
      '<div class="crumb"><a href="#/">首页</a> / <a href="#/a/' + enc(rec.owner || "") + '">' +
        esc(actressName(rec.owner || "未知")) + "</a> / <b>" + esc(w.code) + "</b></div>" +
      '<div class="detail">' +
        '<div class="poster">' + imgTag(w.cover, w.code) + (w.cover ? "" : esc(w.code)) + "</div>" +
        "<div class=\"dinfo\">" +
          "<h1>" + (w.title ? esc(w.title) : esc(w.code)) + "</h1>" +
          '<div class="code">' + esc(w.code) + "</div>" +
          rows +
          (tagHtml ? '<div class="tags">' + tagHtml + "</div>" : "") +
          (ext ? '<div class="extwrap">' + ext + "</div>" : "") +
        "</div>" +
      "</div>" +
      (w.synopsis ? '<section class="block"><div class="block-head"><h2>剧情简介</h2></div>' +
        '<p class="synopsis">' + esc(w.synopsis) + "</p></section>" : "")
    );
  }

  /* =================================================================
     视图：筛选（标签 / 片商 / 系列）
     ================================================================= */
  function viewFilter(type, value) {
    var label = { t: "标签", m: "片商 / 厂牌", s: "系列" }[type];
    var recs = WORKS.filter(function (r) {
      var w = r.w;
      if (type === "t") return (w.labels || []).concat(w.tags || []).indexOf(value) >= 0;
      if (type === "m") return w.maker === value || w.label === value;
      if (type === "s") return w.series === value;
      return false;
    });
    var head = (type === "t" ? "#/t/" : type === "m" ? "#/m/" : "#/s/") + enc(value);
    return (
      '<div class="crumb"><a href="#/">首页</a> / ' + label + ' / <b>' + esc(value) + "</b></div>" +
      '<div class="block-head"><h2>' + esc(label) + "：" + esc(type === "t" ? tagName(value) : value) + "</h2>" +
        '<span class="muted">' + recs.length + " 部</span></div>" +
      sortControls("date_desc") +
      '<div id="gridwrap">' + gridHtml(recs.sort(SORTERS.date_desc)) + "</div>"
    );
  }

  /* =================================================================
     视图：搜索
     ================================================================= */
  function viewSearch(q) {
    q = (q || "").trim().toLowerCase();
    if (!q) {
      // 无关键词：展示全部（按最新）
      var all = WORKS.slice().sort(SORTERS.date_desc);
      return (
        '<div class="crumb"><a href="#/">首页</a> / 全部作品</div>' +
        '<div class="block-head"><h2>全部作品</h2><span class="muted">' + all.length + " 部</span></div>" +
        sortControls("date_desc") +
        '<div id="gridwrap">' + gridHtml(all) + "</div>"
      );
    }
    var recs = WORKS.filter(function (r) { return workMatchesQuery(r, q); });
    return (
      '<div class="crumb"><a href="#/">首页</a> / 搜索：<b>' + esc(q) + "</b></div>" +
      '<div class="block-head"><h2>搜索结果</h2><span class="muted">' + recs.length + " 部</span></div>" +
      sortControls("date_desc") +
      '<div id="gridwrap">' + gridHtml(recs.sort(SORTERS.date_desc)) + "</div>"
    );
  }

  function row(label, val) {
    return '<div class="row"><b>' + esc(label) + "：</b>" + val + "</div>";
  }

  /* =================================================================
     路由
     ================================================================= */
  function router() {
    var app = $("app");
    var h = (location.hash || "#/").slice(1);
    var parts = h.split("/").filter(Boolean); // 去掉空段
    var main = parts[0] || "";
    var param = dec(parts.slice(1).join("/"));

    var html;
    if (main === "" || main === "/") html = viewHome();
    else if (main === "a") html = viewActress(param);
    else if (main === "w") html = viewWork(param);
    else if (main === "t") html = viewFilter("t", param);
    else if (main === "m") html = viewFilter("m", param);
    else if (main === "s") html = viewFilter("s", param);
    else if (main === "q") html = viewSearch(param);
    else html = '<div class="empty">未知页面：' + esc(h) + "</div>";

    app.innerHTML = html;
    window.scrollTo(0, 0);

    // 绑定排序下拉
    var sel = $("sortsel");
    if (sel) {
      sel.addEventListener("change", function () {
        var wrap = $("gridwrap");
        if (!wrap) return;
        // 重新取当前视图的 recs
        var recs = currentRecs(main, param);
        wrap.innerHTML = gridHtml(recs.sort(SORTERS[sel.value] || SORTERS.date_desc));
      });
    }
  }

  // 排序需要重新取当前视图作品列表
  function currentRecs(main, param) {
    if (main === "a") {
      var a = null;
      DB.actresses.forEach(function (x) { if (x.name === param) a = x; });
      return (a ? a.works : []).map(function (w) { return BY_CODE[w.code] || { w: w }; });
    }
    if (main === "t") return WORKS.filter(function (r) {
      return (r.w.labels || []).concat(r.w.tags || []).indexOf(param) >= 0; });
    if (main === "m") return WORKS.filter(function (r) {
      return r.w.maker === param || r.w.label === param; });
    if (main === "s") return WORKS.filter(function (r) { return r.w.series === param; });
    if (main === "q") {
      var q = (param || "").trim().toLowerCase();
      if (!q) return WORKS.slice();
      return WORKS.filter(function (r) { return workMatchesQuery(r, q); });
    }
    return WORKS.slice();
  }

  /* ---- 全局搜索框 ---- */
  function bindSearch() {
    var box = $("search");
    if (!box) return;
    box.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        var v = box.value.trim();
        location.hash = v ? "#/q/" + enc(v) : "#/q/";
      }
    });
  }

  /* ---- 启动 ---- */
  window.addEventListener("hashchange", router);
  document.addEventListener("DOMContentLoaded", function () {
    bindSearch();
    router();
  });
  // 若 DOM 已就绪（脚本在 body 末尾）
  if (document.readyState !== "loading") { bindSearch(); router(); }
})();
