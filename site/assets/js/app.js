/* ===================================================================
   jav-idol-db 站点逻辑（资料库 单页 SPA，多语言：默认日本語，可切中文）
   - 读取 window.JAV_DB（scripts/build_index.py 生成），含 zh 中文映射层
   - 数据原文为日文（来源 codeav 等）；默认以日文显示，可一键切换中文。
     中文显示依赖 data/zh.json 的 actress_zh / tag_zh（及可选的 title_zh）；
     无对应中文映射时回退显示原文，绝不臆造。
   - hash 路由：#/ 首页 | #/a/<女优> | #/w/<番号> |
                #/t/<标签> | #/m/<片商> | #/s/<系列> | #/d/<导演> | #/q/<搜索> | #/stats
   - 标签 / 片商 / 系列 / 女优 / 导演 全部可点，跳转筛选视图
   - 纯前端，file:// 双击或 GitHub Pages 均可运行
   =================================================================== */
(function () {
  "use strict";

  var DB = window.JAV_DB || { actresses: [], counts: {} };
  var ZH = (DB.zh || {});
  var ACTRESS_ZH = ZH.actress_zh || {};   // 日文女优名 -> 中文名
  var TAG_ZH = ZH.tag_zh || {};           // 日文标签 -> 中文
  // 反向映射：中文 -> 日文（用于中文搜索命中）
  var ZH_TO_JP_ACTRESS = {};
  Object.keys(ACTRESS_ZH).forEach(function (jp) { ZH_TO_JP_ACTRESS[ACTRESS_ZH[jp]] = jp; });
  var ZH_TO_JP_TAG = {};
  Object.keys(TAG_ZH).forEach(function (jp) { ZH_TO_JP_TAG[TAG_ZH[jp]] = jp; });

  /* =================================================================
     多语言层（默认日本語，可扩展到 en 等更多语言）
     - LANG 持久化于 localStorage('lang')，缺省 'ja'
     - UI[k] 为字符串或函数（函数接收计数/年份参数）
     - 数据显示名（女优/标签/片名）由 actressName/tagName/workTitle 决定
     ================================================================= */
  var LANGS = ["ja", "zh"];
  var LANG = "ja";
  try { LANG = localStorage.getItem("lang") || "ja"; } catch (e) {}
  if (LANGS.indexOf(LANG) < 0) LANG = "ja";

  /* =================================================================
     主题（亮/暗）：持久化于 localStorage('theme')，缺省跟随系统偏好
     ================================================================= */
  var THEMES = ["light", "dark"];
  var THEME = "dark";
  try {
    THEME = localStorage.getItem("theme") ||
      (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  } catch (e) {}
  if (THEMES.indexOf(THEME) < 0) THEME = "dark";
  function applyTheme(t) {
    if (THEMES.indexOf(t) < 0) return;
    THEME = t;
    try { localStorage.setItem("theme", t); } catch (e) {}
    if (document.documentElement) document.documentElement.setAttribute("data-theme", t);
    paintTheme();
  }
  function paintTheme() {
    var btn = $("themebtn");
    if (btn) btn.textContent = (THEME === "dark") ? "☀️" : "🌙";
  }

  var UI = {
    ja: {
      search_ph: "番号 / タイトル / 女優 / タグ で検索…",
      sort_label: "並び替え",
      s_date_desc: "新着順",
      s_date_asc: "古い順",
      s_rating_desc: "評価順",
      s_duration_desc: "長い順",
      s_code_asc: "番号順",
      home_title: "資料庫",
      home_lead: function (a, w) {
        return a + " 名の女優 · " + w + " 本の作品 · 番号 / タイトル / 女優 / タグ で検索、タグ / メーカー / シリーズ で絞り込み";
      },
      stats_link: "統計 / 概要 →",
      actresses: "女優",
      hot_tags: "人気タグ",
      latest: "新着",
      all_works: "すべての作品",
      stats_title: "資料庫概要",
      stats_lead: function (a, w, y0, y1) {
        return a + " 名の女優 · " + w + " 本の作品 · " + y0 + "–" + y1 + " 年";
      },
      s_actresses: "女優",
      s_works: "作品",
      s_rated: "評価済み",
      s_avg: "平均評価",
      s_year: "年度別リリース数",
      s_maker: "メーカー Top 15",
      s_tag: "タグ Top 24",
      s_actress_rank: "女優別作品数 Top 15",
      s_director: "監督 Top 10",
      crumb_actress: "女優",
      crumb_all: "すべての作品",
      crumb_search: "検索",
      crumb_stats: "統計",
      f_aliases: "別名",
      f_birth: "誕生日",
      f_birthplace: "出身地",
      f_blood: "血液型",
      f_height: "身長",
      f_measure: "スリーサイズ",
      f_debut: "デビュー",
      f_agency: "事務所",
      f_works: "作品数",
      f_span: "活動年",
      f_avg: "平均評価",
      f_incomplete: "⚠️ この作品のデータが不完全です。不足：",
      f_cast_date: "発売日",
      f_cast: "出演",
      f_maker: "メーカー",
      f_label: "レーベル",
      f_series: "シリーズ",
      f_duration: "時間",
      f_director: "監督",
      f_rating: "評価",
      f_synopsis: "あらすじ",
      f_bio: "プロフィール",
      flt_t: "タグ",
      flt_m: "メーカー / レーベル",
      flt_s: "シリーズ",
      flt_d: "監督",
      pending_title: "（タイトル未取得）",
      badge_incomplete: "データ不足",
      empty_works: "一致する作品がありません。",
      err_work: "未找到作品：",
      err_actress: "未找到女优：",
      err_page: "未知页面："
    },
    zh: {
      search_ph: "搜索 番号 / 片名 / 女优 / 标签…",
      sort_label: "排序",
      s_date_desc: "最新发行",
      s_date_asc: "最早发行",
      s_rating_desc: "评分最高",
      s_duration_desc: "时长最长",
      s_code_asc: "番号排序",
      home_title: "资料库",
      home_lead: function (a, w) {
        return a + " 位女优 · " + w + " 部作品 · 支持番号 / 片名 / 女优 / 标签检索，标签 / 片商 / 系列 一键筛选";
      },
      stats_link: "资料库总览 / 统计 →",
      actresses: "女优",
      hot_tags: "热门标签",
      latest: "最新发行",
      all_works: "全部作品",
      stats_title: "资料库总览",
      stats_lead: function (a, w, y0, y1) {
        return a + " 位女优 · " + w + " 部作品 · 跨 " + y0 + "–" + y1 + " 年";
      },
      s_actresses: "女优",
      s_works: "作品",
      s_rated: "已评分作品",
      s_avg: "平均评分",
      s_year: "逐年发行量",
      s_maker: "片商 Top 15",
      s_tag: "标签 Top 24",
      s_actress_rank: "女优作品量 Top 15",
      s_director: "导演 Top 10",
      crumb_actress: "女优",
      crumb_all: "全部作品",
      crumb_search: "搜索",
      crumb_stats: "统计",
      f_aliases: "别名",
      f_birth: "生日",
      f_birthplace: "出身地",
      f_blood: "血型",
      f_height: "身高",
      f_measure: "三围",
      f_debut: "出道",
      f_agency: "事务所",
      f_works: "作品数",
      f_span: "活动年份",
      f_avg: "平均评分",
      f_incomplete: "⚠️ 本作资料不全，缺失：",
      f_cast_date: "发行日",
      f_cast: "出演",
      f_maker: "片商",
      f_label: "厂牌",
      f_series: "系列",
      f_duration: "时长",
      f_director: "导演",
      f_rating: "评分",
      f_synopsis: "剧情简介",
      f_bio: "个人简介",
      flt_t: "标签",
      flt_m: "片商 / 厂牌",
      flt_s: "系列",
      flt_d: "导演",
      pending_title: "（片名待抓取）",
      badge_incomplete: "资料不全",
      empty_works: "没有匹配的作品。",
      err_work: "未找到作品：",
      err_actress: "未找到女优：",
      err_page: "未知页面："
    }
  };

  // 取 UI 文案：当前语言优先，缺省回退中文
  function T(key) {
    var d = UI[LANG] || UI.zh;
    var v = d[key];
    if (v === undefined) v = (UI.zh || {})[key];
    return v === undefined ? key : v;
  }

  /* ---- 显示名（随语言切换）---- */
  // 女优：ja 显示原文；zh 显示「中文（日文）」
  function actressName(jp) {
    if (LANG === "zh") {
      var zh = ACTRESS_ZH[jp];
      return zh ? (zh + "（" + jp + "）") : jp;
    }
    return jp;
  }
  // 标签：ja 显示原文；zh 优先全量映射 GLOBAL_TAG_ZH，再回退手工 tag_zh，最后原文
  function tagName(jp) {
    if (LANG === "zh") return GLOBAL_TAG_ZH[jp] || TAG_ZH[jp] || jp;
    return jp;
  }
  // 片名：ja 显示原文；zh 优先显示 title_zh（由 zh.json 提供），缺失则原文
  function workTitle(w) {
    if (LANG === "zh" && w && w.title_zh) return w.title_zh;
    return (w && w.title) || "";
  }

  // 中文感知搜索：q 已 lowercased；命中 番号/片名/女优(中或日)/厂牌/系列/标签(中或日)
  function workMatchesQuery(r, q) {
    if (!q) return true;
    var w = r.w;
    if ((w.code || "").toLowerCase().indexOf(q) >= 0) return true;
    var t = workTitle(w);
    if (t && t.toLowerCase().indexOf(q) >= 0) return true;
    var o = r.owner || "";
    if (o.toLowerCase().indexOf(q) >= 0) return true;
    if ((ACTRESS_ZH[o] || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.actress_search || []).some(function (x) { return x.toLowerCase().indexOf(q) >= 0; })) return true;
    if ((w.maker || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.label || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.series || "").toLowerCase().indexOf(q) >= 0) return true;
    if ((w.tags || []).some(function (x) {
      return x.toLowerCase().indexOf(q) >= 0 || ((GLOBAL_TAG_ZH[x] || TAG_ZH[x] || "").toLowerCase().indexOf(q) >= 0);
    })) return true;
    if ((w.tags_zh || []).some(function (x) { return x.toLowerCase().indexOf(q) >= 0; })) return true;
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

  // 全量 JP->ZH 标签映射：由每条作品的 tags / tags_zh 并行构建（genre_norm 已产出中文）
  // 覆盖率 ~99.98%；不足时回退到 zh.json 手工 tag_zh 与原文。
  var GLOBAL_TAG_ZH = {};
  DB.actresses.forEach(function (a) {
    (a.works || []).forEach(function (w) {
      var ts = w.tags || [], tz = w.tags_zh || [];
      if (ts.length && tz.length && ts.length === tz.length) {
        for (var i = 0; i < ts.length; i++) {
          if (ts[i] && tz[i] && !(ts[i] in GLOBAL_TAG_ZH)) GLOBAL_TAG_ZH[ts[i]] = tz[i];
        }
      }
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
      ["date_desc", T("s_date_desc")], ["date_asc", T("s_date_asc")],
      ["rating_desc", T("s_rating_desc")], ["duration_desc", T("s_duration_desc")], ["code_asc", T("s_code_asc")]
    ];
    var html = '<div class="sortbar"><label>' + T("sort_label") + '</label><select id="sortsel">';
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
    var incomplete = w.incomplete ? '<span class="badge warn">' + T("badge_incomplete") + "</span>" : "";
    var title = workTitle(w) ? esc(workTitle(w)) : T("pending_title");
    return (
      '<a class="card" href="#/w/' + enc(w.code) + '">' +
        '<div class="thumb">' +
          imgTag(w.cover, w.code, "cover-img") +
          (w.cover ? "" : '<span class="ph">' + esc(w.code) + "</span>") +
          rating +
          incomplete +
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
        '<div class="sub">' + (a.work_count || 0) + " " + T("f_works") + "</div></div></a>"
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
    if (!recs.length) return '<div class="empty">' + T("empty_works") + "</div>";
    return '<div class="grid">' + recs.map(workCard).join("") + "</div>";
  }

  /* =================================================================
     视图：首页
     ================================================================= */
  function viewHome() {
    var acts = DB.actresses;
    var recent = WORKS.slice().sort(SORTERS.date_desc);
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
        '<h1>' + esc(T("home_title")) + "</h1>" +
        '<p class="lead">' + esc(T("home_lead")((DB.counts.actresses || acts.length), WORKS.length)) + "</p>" +
      "</section>" +

      '<div class="quickrow"><a class="qlink" href="#/stats">' + esc(T("stats_link")) + "</a></div>" +

      '<section class="block">' +
        '<div class="block-head"><h2>' + esc(T("actresses")) + '</h2><span class="muted">' + acts.length + " " + esc(T("actresses")) + "</span></div>" +
        '<div class="grid actress-grid">' + acts.map(actressCard).join("") + "</div>" +
      "</section>" +

      (hotTags.length ? '<section class="block">' +
        '<div class="block-head"><h2>' + esc(T("hot_tags")) + "</h2></div>" +
        '<div class="chipcloud">' + hotTags.map(function (t) { return chip("t", t); }).join("") + "</div>" +
      "</section>" : "") +

      '<section class="block">' +
        '<div class="block-head"><h2>' + esc(T("latest")) + "</h2>" +
          '<a class="more" href="#/q/">' + esc(T("all_works")) + " →</a></div>" +
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
    if (!a) return '<div class="empty">' + esc(T("err_actress")) + esc(name) + "</div>";
    var ds = (a.works || []).map(function (w) { return (w.date || "").slice(0, 4); }).filter(Boolean).sort();
    var span = ds.length ? (ds[0] + "–" + ds[ds.length - 1]) : "—";
    var rs = (a.works || []).filter(function (w) { return w.rating; });
    var avg = rs.length ? (rs.reduce(function (s, w) { return s + w.rating; }, 0) / rs.length).toFixed(1) : null;
    var recs = (a.works || []).map(function (w) { return BY_CODE[w.code] || { w: w, owner: a.name }; });
    return (
      '<div class="crumb"><a href="#/">' + esc(T("home_title")) + '</a> / ' + esc(T("crumb_actress")) + " / <b>" + esc(a.name) + "</b></div>" +
      '<div class="profile">' +
        '<div class="avatar">' + imgTag(a.avatar, a.name) + (a.avatar ? "" : esc(actressName(a.name))) + "</div>" +
        "<div class=\"pinfo\">" +
          "<h1>" + esc(actressName(a.name)) + "</h1>" +
          (a.aliases && a.aliases.length ? '<div class="row">' + esc(T("f_aliases")) + '：' + a.aliases.map(esc).join("、") + "</div>" : "") +
          (a.birthdate ? '<div class="row">' + esc(T("f_birth")) + '：' + esc(a.birthdate) + "</div>" : "") +
          (a.birthplace ? '<div class="row">' + esc(T("f_birthplace")) + '：' + esc(a.birthplace) + "</div>" : "") +
          (a.blood_type ? '<div class="row">' + esc(T("f_blood")) + '：' + esc(a.blood_type) + "</div>" : "") +
          (a.height ? '<div class="row">' + esc(T("f_height")) + "：" + esc(a.height) + " cm</div>" : "") +
          (a.measurements ? '<div class="row">' + esc(T("f_measure")) + '：' + esc(a.measurements) + (a.cup ? "（" + esc(a.cup) + "杯）" : "") + "</div>" : "") +
          (a.debut_year ? '<div class="row">' + esc(T("f_debut")) + "：" + esc(a.debut_year) + " 年</div>" : "") +
          (a.agency ? '<div class="row">' + esc(T("f_agency")) + '：' + esc(a.agency) + "</div>" : "") +
          '<div class="row">' + esc(T("f_works")) + "：" + (a.work_count || 0) + " " + esc(T("f_works")) + "</div>" +
          (ds.length ? '<div class="row">' + esc(T("f_span")) + "：" + esc(span) + "</div>" : "") +
          (avg ? '<div class="row">' + esc(T("f_avg")) + "：★ " + avg + "（" + rs.length + " " + esc(T("f_works")) + "）</div>" : "") +
        "</div>" +
      "</div>" +
      (a.bio ? '<section class="block bio-block"><div class="block-head"><h2>' + esc(T("f_bio")) + '</h2></div><p class="synopsis">' + esc(a.bio) + "</p></section>" : "") +
      '<div class="block-head"><h2>' + esc(T("actresses")) + " " + esc(T("f_works")) + '</h2><span class="muted">' + recs.length + " " + esc(T("f_works")) + "</span></div>" +
      sortControls("date_desc") +
      '<div id="gridwrap">' + gridHtml(recs.sort(SORTERS.date_desc)) + "</div>"
    );
  }

  /* =================================================================
     视图：资料库总览统计
     ================================================================= */
  function viewStats() {
    var years = {}, makers = {}, tags = {}, directors = {};
    var rated = 0, ratingSum = 0;
    WORKS.forEach(function (r) {
      var w = r.w;
      var y = (w.date || "").slice(0, 4);
      if (y) years[y] = (years[y] || 0) + 1;
      if (w.maker) makers[w.maker] = (makers[w.maker] || 0) + 1;
      if (w.director) directors[w.director] = (directors[w.director] || 0) + 1;
      (w.tags || []).forEach(function (t) { tags[t] = (tags[t] || 0) + 1; });
      if (w.rating) { rated++; ratingSum += w.rating; }
    });
    var yearKeys = Object.keys(years).sort();
    var yMin = yearKeys.length ? yearKeys[0] : "—";
    var yMax = yearKeys.length ? yearKeys[yearKeys.length - 1] : "—";
    var yMaxCount = yearKeys.length ? Math.max.apply(null, yearKeys.map(function (k) { return years[k]; })) : 1;

    function topMap(obj, n) {
      return Object.keys(obj).sort(function (a, b) { return obj[b] - obj[a]; }).slice(0, n);
    }
    function barRow(k, v, max) {
      var pct = max ? Math.round(v / max * 100) : 0;
      return '<div class="bar-row"><span class="bar-lbl">' + esc(k) + '</span>' +
        '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
        '<span class="bar-val">' + v + "</span></div>";
    }

    var topMakers = topMap(makers, 15);
    var topTags = topMap(tags, 24);
    var topDirectors = topMap(directors, 10);
    var actressRank = DB.actresses.slice().sort(function (a, b) {
      return (b.works ? b.works.length : 0) - (a.works ? a.works.length : 0);
    }).slice(0, 15);

    var html =
      '<section class="hero"><h1>' + esc(T("stats_title")) + '</h1>' +
        '<p class="lead">' + esc(T("stats_lead")((DB.counts.actresses || DB.actresses.length), WORKS.length, yMin, yMax)) + "</p></section>" +

      '<section class="block stats-grid">' +
        '<div class="stat-card"><div class="num">' + (DB.counts.actresses || DB.actresses.length) + '</div><div class="lbl">' + esc(T("s_actresses")) + '</div></div>' +
        '<div class="stat-card"><div class="num">' + WORKS.length + '</div><div class="lbl">' + esc(T("s_works")) + '</div></div>' +
        '<div class="stat-card"><div class="num">' + rated + '</div><div class="lbl">' + esc(T("s_rated")) + '</div></div>' +
        '<div class="stat-card"><div class="num">' + (rated ? (ratingSum / rated).toFixed(1) : "—") + '</div><div class="lbl">' + esc(T("s_avg")) + '</div></div>' +
      "</section>" +

      '<section class="block"><div class="block-head"><h2>' + esc(T("s_year")) + '</h2></div>' +
        '<div class="bars">' + yearKeys.map(function (k) { return barRow(k, years[k], yMaxCount); }).join("") + "</div></section>" +

      '<section class="block"><div class="block-head"><h2>' + esc(T("s_maker")) + '</h2></div>' +
        '<ol class="rank">' + topMakers.map(function (m) {
          return '<li><a href="#/m/' + enc(m) + '">' + esc(m) + '</a><span class="rc">' + makers[m] + "</span></li>";
        }).join("") + "</ol></section>" +

      '<section class="block"><div class="block-head"><h2>' + esc(T("s_tag")) + '</h2></div>' +
        '<div class="chipcloud">' + topTags.map(function (t) { return chip("t", t); }).join("") + "</div></section>" +

      '<section class="block"><div class="block-head"><h2>' + esc(T("s_actress_rank")) + '</h2></div>' +
        '<ol class="rank">' + actressRank.map(function (a) {
          return '<li><a href="#/a/' + enc(a.name) + '">' + esc(actressName(a.name)) + '</a><span class="rc">' + (a.works ? a.works.length : 0) + "</span></li>";
        }).join("") + "</ol></section>" +

      (topDirectors.length ? '<section class="block"><div class="block-head"><h2>' + esc(T("s_director")) + '</h2></div>' +
        '<ol class="rank">' + topDirectors.map(function (d) {
          return '<li><a href="#/d/' + enc(d) + '">' + esc(d) + '</a><span class="rc">' + directors[d] + "</span></li>";
        }).join("") + "</ol></section>" : "");
    return html;
  }

  /* =================================================================
     视图：作品详情
     ================================================================= */
  function viewWork(code) {
    var rec = BY_CODE[code];
    if (!rec) return '<div class="empty">' + esc(T("err_work")) + esc(code) + "</div>";
    var w = rec.w;
    var rows = "";
    var incompleteNote = "";
    if (w.incomplete) {
      var mf = (w.missing_fields || []).join("、") || "部分可选字段";
      incompleteNote = '<div class="incomplete-note">' + esc(T("f_incomplete")) + esc(mf) + "</div>";
    }
    if (w.date) rows += row(T("f_cast_date"), w.date);
    var castList = (w.actresses && w.actresses.length) ? w.actresses : (rec.owner ? [rec.owner] : []);
    if (castList.length) {
      var castHtml = castList.map(function (n) {
        return '<a href="#/a/' + enc(n) + '">' + esc(actressName(n)) + "</a>";
      }).join("、");
      rows += '<div class="row"><b>' + esc(T("f_cast")) + '：</b>' + castHtml + "</div>";
    }
    if (w.maker) rows += '<div class="row"><b>' + esc(T("f_maker")) + '：</b>' + chip("m", w.maker) + "</div>";
    if (w.label) rows += '<div class="row"><b>' + esc(T("f_label")) + '：</b>' + chip("m", w.label) + "</div>";
    if (w.series) rows += '<div class="row"><b>' + esc(T("f_series")) + '：</b>' + chip("s", w.series) + "</div>";
    if (w.duration) rows += row(T("f_duration"), w.duration + " " + (LANG === "zh" ? "分钟" : "分"));
    if (w.director) rows += '<div class="row"><b>' + esc(T("f_director")) + '：</b>' + chip("d", w.director) + "</div>";
    if (w.rating) rows += row(T("f_rating"), "★ " + w.rating + (w.rating_count ? "（" + w.rating_count + (LANG === "zh" ? " 评价" : " 評価") + "）" : ""));

    // 标签：统一用原始 tags，显示名经 tagName 按语言切换（zh 走全量映射）
    var tagList = (w.labels || []).concat(w.tags || []);
    var tagHtml = chips("t", tagList);

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
    if (w.source_url) {
      var srcLabel = w.source
        ? (LANG === "zh" ? "在 " + w.source + " 查看" : w.source + " で見る")
        : (LANG === "zh" ? "数据源" : "データソース");
      ext += '<a class="extbtn" href="' + esc(w.source_url) + '" target="_blank" rel="noopener">' + esc(srcLabel) + " ↗</a>";
    }
    if (w.code) ext += '<a class="extbtn" href="https://www.dmm.co.jp/search/=/searchstr=' + enc(w.code) + '" target="_blank" rel="noopener">在 DMM 搜索 ↗</a>';

    return (
      '<div class="crumb"><a href="#/">' + esc(T("home_title")) + '</a> / <a href="#/a/' + enc(rec.owner || "") + '">' +
        esc(actressName(rec.owner || "未知")) + "</a> / <b>" + esc(w.code) + "</b></div>" +
      '<div class="detail">' +
        '<div class="poster">' + imgTag(w.cover, w.code) + (w.cover ? "" : esc(w.code)) + "</div>" +
        "<div class=\"dinfo\">" +
          "<h1>" + (workTitle(w) ? esc(workTitle(w)) : esc(w.code)) + "</h1>" +
          '<div class="code">' + esc(w.code) + "</div>" +
          incompleteNote +
          rows +
          (tagHtml ? '<div class="tags">' + tagHtml + "</div>" : "") +
          (ext ? '<div class="extwrap">' + ext + "</div>" : "") +
        "</div>" +
      "</div>" +
      (w.synopsis ? '<section class="block"><div class="block-head"><h2>' + esc(T("f_synopsis")) + '</h2></div>' +
        '<p class="synopsis">' + esc(w.synopsis) + "</p></section>" : "")
    );
  }

  /* =================================================================
     视图：筛选（标签 / 片商 / 系列 / 导演）
     ================================================================= */
  function viewFilter(type, value) {
    var label = { t: T("flt_t"), m: T("flt_m"), s: T("flt_s"), d: T("flt_d") }[type];
    var recs = WORKS.filter(function (r) {
      var w = r.w;
      if (type === "t") return (w.labels || []).concat(w.tags || [], w.tags_zh || []).indexOf(value) >= 0;
      if (type === "m") return w.maker === value || w.label === value;
      if (type === "s") return w.series === value;
      if (type === "d") return (w.director || "") === value;
      return false;
    });
    var head = (type === "t" ? "#/t/" : type === "m" ? "#/m/" : type === "s" ? "#/s/" : "#/d/") + enc(value);
    return (
      '<div class="crumb"><a href="#/">' + esc(T("home_title")) + '</a> / ' + esc(label) + " / <b>" + esc(value) + "</b></div>" +
      '<div class="block-head"><h2>' + esc(label) + "：" + esc(type === "t" ? tagName(value) : value) + "</h2>" +
        '<span class="muted">' + recs.length + " " + esc(T("f_works")) + "</span></div>" +
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
      var all = WORKS.slice().sort(SORTERS.date_desc);
      return (
        '<div class="crumb"><a href="#/">' + esc(T("home_title")) + '</a> / ' + esc(T("crumb_all")) + "</div>" +
        '<div class="block-head"><h2>' + esc(T("all_works")) + '</h2><span class="muted">' + all.length + " " + esc(T("f_works")) + "</span></div>" +
        sortControls("date_desc") +
        '<div id="gridwrap">' + gridHtml(all) + "</div>"
      );
    }
    var recs = WORKS.filter(function (r) { return workMatchesQuery(r, q); });
    return (
      '<div class="crumb"><a href="#/">' + esc(T("home_title")) + '</a> / ' + esc(T("crumb_search")) + '：<b>' + esc(q) + "</b></div>" +
      '<div class="block-head"><h2>' + esc(T("f_results")) + '</h2><span class="muted">' + recs.length + " " + esc(T("f_works")) + "</span></div>" +
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
    else if (main === "d") html = viewFilter("d", param);
    else if (main === "q") html = viewSearch(param);
    else if (main === "stats") html = viewStats();
    else html = '<div class="empty">' + esc(T("err_page")) + esc(h) + "</div>";

    app.innerHTML = html;
    window.scrollTo(0, 0);

    // 绑定排序下拉
    var sel = $("sortsel");
    if (sel) {
      sel.addEventListener("change", function () {
        var wrap = $("gridwrap");
        if (!wrap) return;
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
      return (r.w.labels || []).concat(r.w.tags || [], r.w.tags_zh || []).indexOf(param) >= 0; });
    if (main === "m") return WORKS.filter(function (r) {
      return r.w.maker === param || r.w.label === param; });
    if (main === "s") return WORKS.filter(function (r) { return r.w.series === param; });
    if (main === "d") return WORKS.filter(function (r) { return (r.w.director || "") === param; });
    if (main === "q") {
      var q = (param || "").trim().toLowerCase();
      if (!q) return WORKS.slice();
      return WORKS.filter(function (r) { return workMatchesQuery(r, q); });
    }
    return WORKS.slice();
  }

  /* ---- 语言下拉 ---- */
  var langOpen = false;
  function paintLang() {
    var lbl = $("langlabel");
    if (lbl) lbl.textContent = (LANG === "zh") ? "中文" : "日本語";
    var menu = $("langmenu");
    if (menu) {
      var items = menu.querySelectorAll("li");
      for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle("active", items[i].getAttribute("data-lang") === LANG);
      }
    }
  }
  function openLang(open) {
    langOpen = open;
    var dd = $("langdd");
    if (dd) dd.classList.toggle("open", open);
    var btn = $("langbtn");
    if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  function applyLang(l) {
    if (LANGS.indexOf(l) < 0) return;
    LANG = l;
    try { localStorage.setItem("lang", l); } catch (e) {}
    if (document.documentElement) document.documentElement.lang = (l === "zh") ? "zh-CN" : "ja";
    openLang(false);
    paintLang();
    var sb = $("search");
    if (sb) sb.placeholder = T("search_ph");
    router();
  }
  function bindLang() {
    var dd = $("langdd");
    if (!dd) return;
    dd.addEventListener("click", function (e) {
      var li = e.target.closest ? e.target.closest("li[data-lang]") : null;
      if (li) { applyLang(li.getAttribute("data-lang")); return; }
      if (e.target.closest && e.target.closest("#langbtn")) openLang(!langOpen);
    });
    document.addEventListener("click", function (e) {
      if (langOpen && dd && !dd.contains(e.target)) openLang(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && langOpen) openLang(false);
    });
  }

  /* ---- 主题切换 ---- */
  function bindTheme() {
    var btn = $("themebtn");
    if (!btn) return;
    btn.addEventListener("click", function () {
      applyTheme(THEME === "dark" ? "light" : "dark");
    });
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
  function boot() {
    if (document.documentElement) document.documentElement.lang = (LANG === "zh") ? "zh-CN" : "ja";
    paintTheme();
    paintLang();
    var sb = $("search");
    if (sb) sb.placeholder = T("search_ph");
    bindSearch();
    bindLang();
    bindTheme();
    router();
  }
  document.addEventListener("DOMContentLoaded", boot);
  // 若 DOM 已就绪（脚本在 body 末尾）
  if (document.readyState !== "loading") { boot(); }
})();
