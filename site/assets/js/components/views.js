// components/views.js — 各路由页面视图
// 每个函数返回 HTML 字符串；作品类视图通过 worksSection() 统一套用 工具条 + 网格，
// 并把当前列表存入 viewState 供排序刷新复用。

import { esc, imgTag, enc } from "../core/util.js";
import { T, actressName, tagName, workTitle, statusText, statusClass, workMatchesQuery } from "../core/i18n.js";
import { getLang } from "../core/state.js";
import { WORKS, actressCount, workCount, filterByType, searchWorks, actressByName, BY_CODE } from "../core/data.js";
import { workGrid, actressGrid, chip, chips } from "./cards.js";
import { toolbar, SORTERS } from "./toolbar.js";
import { buildExtButtons } from "../core/sources.js";

// 当前作品视图的列表与排序（排序下拉刷新时由 main.js 复用）
export var viewState = { recs: [], sort: "date_desc" };

/** 作品区：工具条 + 网格（写入 viewState 供排序刷新） */
function worksSection(recs, sortValue, showView) {
  viewState.recs = recs;
  viewState.sort = sortValue || "date_desc";
  var sorted = recs.slice().sort(SORTERS[viewState.sort] || SORTERS.date_desc);
  return toolbar({ count: recs.length, showView: showView !== false, showSort: true, sortValue: viewState.sort }) +
    '<div id="gridwrap">' + workGrid(sorted) + "</div>";
}

/* ============================ 首页 ============================ */
export function home() {
  var recent = WORKS.slice().sort(SORTERS.date_desc);
  var latest = recent.slice(0, 60);

  // 热门标签
  var tagCount = {};
  WORKS.forEach(function (r) { (r.w.tags || []).forEach(function (t) { tagCount[t] = (tagCount[t] || 0) + 1; }); });
  var hotTags = Object.keys(tagCount).sort(function (a, b) { return tagCount[b] - tagCount[a]; }).slice(0, 24);

  // 新晋女优（按作品最新发行倒推，取前 12）
  var acts = DB_actresses().slice().sort(function (a, b) {
    return (b.works && b.works[0] && b.works[0].date || "").localeCompare((a.works && a.works[0] && a.works[0].date) || "");
  }).slice(0, 12);

  return (
    '<section class="hero"><h1>' + esc(T("brand")) + "</h1>" +
      '<p class="lead">' + esc(T("home_lead")(actressCount(), workCount())) + "</p></section>" +

    '<a class="qlink" href="#/stats" style="display:inline-block;margin:4px 2px 18px;color:var(--accent-text);font-weight:600">' + esc(T("stats_link")) + "</a>" +

    '<section class="block"><div class="block-head"><h2>' + esc(T("new_actresses")) + "</h2>" +
      '<span class="muted">' + actressCount() + " " + esc(T("actresses")) + '</span>' +
      '<a class="more" href="#/actresses">→</a></div>' +
      actressGrid(acts) + "</section>" +

    (hotTags.length ? '<section class="block"><div class="block-head"><h2>' + esc(T("hot_tags")) + "</h2></div>" +
      '<div class="chipcloud">' + hotTags.map(function (t) { return chip("t", t); }).join("") + "</div></section>" : "") +

    '<section class="block"><div class="block-head"><h2>' + esc(T("latest")) + "</h2>" +
      '<a class="more" href="#/q/">' + esc(T("all_works")) + " →</a></div>" +
      worksSection(latest, "date_desc", true) + "</section>"
  );
}

// 取女优数组（data.js 未直接导出 actress 列表，这里从 WORKS 反推较贵；改为从 DB 读）
function DB_actresses() { return (window.JAV_DB && window.JAV_DB.actresses) || []; }

/* ============================ 女优总览 ============================ */
export function actressList() {
  var acts = DB_actresses().slice().sort(function (a, b) { return (b.work_count || 0) - (a.work_count || 0); });
  return (
    '<div class="crumb">' + esc(T("nav_actresses")) + "</div>" +
    '<div class="block-head"><h2>' + esc(T("actresses")) + '</h2><span class="muted">' + acts.length + " " + esc(T("actresses")) + "</span></div>" +
    actressGrid(acts)
  );
}

/* =====================  facet 浏览（标签/片商/系列/导演） ===================== */
export function browseFacet(kind) {
  var map = {};
  WORKS.forEach(function (r) {
    var w = r.w;
    if (kind === "tags") (w.tags || []).forEach(function (v) { map[v] = (map[v] || 0) + 1; });
    else if (kind === "makers") [w.maker, w.label].forEach(function (v) { if (v) map[v] = (map[v] || 0) + 1; });
    else if (kind === "series") { if (w.series) map[w.series] = (map[w.series] || 0) + 1; }
    else if (kind === "directors") { if (w.director) map[w.director] = (map[w.director] || 0) + 1; }
  });
  var keys = Object.keys(map).sort(function (a, b) { return map[b] - map[a]; });
  // 不同 facet 用不同路由前缀与展示名
  var routeOf = { tags: "#/t/", makers: "#/m/", series: "#/s/", directors: "#/d/" }[kind];
  var labelKey = { tags: "nav_tags", makers: "nav_makers", series: "nav_series", directors: "nav_directors" }[kind];
  var dispOf = function (v) { return kind === "tags" ? tagName(v) : v; };

  var cloud = keys.slice(0, 80).map(function (v) {
    return '<a class="chip" href="' + routeOf + enc(v) + '">' + esc(dispOf(v)) +
      ' <span style="color:var(--muted);font-weight:500">' + map[v] + "</span></a>";
  }).join("");

  return (
    '<div class="crumb">' + esc(T("nav_library")) + " / <b>" + esc(T(labelKey)) + "</b></div>" +
    '<div class="block-head"><h2>' + esc(T(labelKey)) + '</h2><span class="muted">' + keys.length + "</span></div>" +
    '<div class="chipcloud">' + (cloud || '<span class="muted">—</span>') + "</div>"
  );
}

/* ============================ 筛选（t/m/s/d） ============================ */
export function filterView(type, value) {
  var labelKey = { t: "flt_t", m: "flt_m", s: "flt_s", d: "flt_d" }[type];
  var recs = filterByType(type, value);
  return (
    '<div class="crumb"><a href="#/">' + esc(T("brand")) + "</a><span class=\"sep\">/</span>" + esc(T(labelKey)) +
      ' / <b>' + esc(type === "t" ? tagName(value) : value) + "</b></div>" +
    '<div class="block-head"><h2>' + esc(type === "t" ? tagName(value) : value) + '</h2><span class="muted">' + recs.length + " " + esc(T("f_works")) + "</span></div>" +
    worksSection(recs, "date_desc", true)
  );
}

/* ============================ 搜索 ============================ */
export function searchView(q) {
  q = (q || "").trim();
  if (!q) {
    return (
      '<div class="crumb"><a href="#/">' + esc(T("brand")) + "</a><span class=\"sep\">/</span>" + esc(T("crumb_all")) + "</div>" +
      '<div class="block-head"><h2>' + esc(T("nav_works")) + '</h2><span class="muted">' + workCount() + " " + esc(T("f_works")) + "</span></div>" +
      worksSection(WORKS.slice(), "date_desc", true)
    );
  }
  var recs = searchWorks(q, workMatchesQuery);
  return (
    '<div class="crumb"><a href="#/">' + esc(T("brand")) + '</a><span class="sep">/</span>' + esc(T("crumb_search")) + '：<b>' + esc(q) + "</b></div>" +
    '<div class="block-head"><h2>' + esc(T("results")) + '</h2><span class="muted">' + recs.length + " " + esc(T("f_works")) + "</span></div>" +
    worksSection(recs, "date_desc", true)
  );
}

/* ============================ 女优详情 ============================ */
export function actressDetail(name) {
  var a = actressByName(name);
  if (!a) return '<div class="empty">' + esc(T("err_actress")) + esc(name) + "</div>";
  var ds = (a.works || []).map(function (w) { return (w.date || "").slice(0, 4); }).filter(Boolean).sort();
  var span = ds.length ? (ds[0] + "–" + ds[ds.length - 1]) : "—";
  var rs = (a.works || []).filter(function (w) { return w.rating; });
  var avg = rs.length ? (rs.reduce(function (s, w) { return s + w.rating; }, 0) / rs.length).toFixed(1) : null;
  var recs = (a.works || []).map(function (w) { return BY_CODE[w.code] || { w: w, owner: a.name }; });

  function row(label, val) { return '<div class="row"><b>' + esc(label) + "：</b>" + val + "</div>"; }

  return (
    '<div class="crumb"><a href="#/">' + esc(T("brand")) + '</a><span class="sep">/</span>' + esc(T("crumb_actress")) + ' / <b>' + esc(a.name) + "</b></div>" +
    '<div class="profile">' +
      '<div class="avatar">' + imgTag(a.avatar, a.name) + (a.avatar ? "" : esc(actressName(a.name))) + "</div>" +
      "<div class=\"pinfo\"><h1>" + esc(actressName(a.name)) + "</h1>" +
        '<span class="status-badge ' + statusClass(a.status) + '">' + esc(statusText(a.status)) + "</span>" +
        ((a.reading || a.roman_name) ? '<div class="row sub-name">' +
          (a.reading ? esc(a.reading) : "") + (a.reading && a.roman_name ? " / " : "") + (a.roman_name ? esc(a.roman_name) : "") + "</div>" : "") +
        (a.aliases && a.aliases.length ? row(T("f_aliases"), a.aliases.map(esc).join("、")) : "") +
        (a.birthdate ? row(T("f_birth"), esc(a.birthdate)) : "") +
        (a.birthplace ? row(T("f_birthplace"), esc(a.birthplace)) : "") +
        (a.blood_type ? row(T("f_blood"), esc(a.blood_type)) : "") +
        (a.height ? row(T("f_height"), esc(a.height) + " cm") : "") +
        (a.measurements ? row(T("f_measure"), esc(a.measurements) + (a.cup ? "（" + esc(a.cup) + "杯）" : "")) : "") +
        (a.debut_date ? row(T("f_debut"), esc(a.debut_date)) : (a.debut_year ? row(T("f_debut"), esc(a.debut_year) + " 年") : "")) +
        (a.retire_date ? row(T("f_retire"), esc(a.retire_date)) : "") +
        (a.comeback_date ? row(T("f_comeback"), esc(a.comeback_date)) : "") +
        (a.career_periods ? row(T("f_career"), esc(a.career_periods)) : "") +
        (a.agency ? row(T("f_agency"), esc(a.agency)) : "") +
        (a.hobby ? row(T("f_hobby"), esc(a.hobby)) : "") +
        (a.debut_work ? row(T("f_debut_work"), esc(a.debut_work)) : "") +
        (a.blog ? row(T("f_blog"), '<a href="' + esc(a.blog) + '" target="_blank" rel="noopener">' + esc(a.blog) + "</a>") : "") +
        (a.official_site ? row(T("f_site"), '<a href="' + esc(a.official_site) + '" target="_blank" rel="noopener">' + esc(a.official_site) + "</a>") : "") +
        (a.minnano_url ? row(T("f_minnano"), '<a href="' + esc(a.minnano_url) + '" target="_blank" rel="noopener">minnano-av.com ↗</a>') : "") +
        (a.name_zh ? row(T("f_name_zh"), esc(a.name_zh)) : "") +
        (a.aliases_zh && a.aliases_zh.length ? row(T("f_aliases_zh"), a.aliases_zh.map(esc).join("、")) : "") +
        (a.notable_work ? row(T("f_notable"), esc(a.notable_work)) : "") +
        (a.baike_url
          ? row(T("f_baike"), '<a href="' + esc(a.baike_url) + '" target="_blank" rel="noopener">baike.baidu.com ↗</a>')
          : row(T("f_baike"), '<a href="https://baike.baidu.com/search?word=' + enc(a.name_zh || actressName(a.name)) + '" target="_blank" rel="noopener">' + esc(T("f_baike_search")) + " ↗</a>")) +
        (a.status_source ? row(T("f_status_src"), esc(a.status_source)) : "") +
        row(T("f_works"), (a.work_count || 0) + " " + T("f_works")) +
        (ds.length ? row(T("f_span"), esc(span)) : "") +
        (avg ? row(T("f_avg"), "★ " + avg + "（" + rs.length + " " + T("f_works") + "）") : "") +
      "</div></div>" +
    (a.bio ? '<section class="block bio-block"><div class="block-head"><h2>' + esc(T("f_bio")) + '</h2></div><p class="synopsis">' + esc(a.bio) + "</p></section>" : "") +
    '<div class="block-head"><h2>' + esc(T("actresses")) + " " + esc(T("f_works")) + '</h2><span class="muted">' + recs.length + " " + esc(T("f_works")) + "</span></div>" +
    worksSection(recs, "date_desc", true)
  );
}

/* ============================ 作品详情 ============================ */
export function workDetail(code) {
  var rec = BY_CODE[code];
  if (!rec) return '<div class="empty">' + esc(T("err_work")) + esc(code) + "</div>";
  var w = rec.w;
  var rows = "";
  if (w.incomplete) {
    var mf = (w.missing_fields || []).join("、") || "部分可选字段";
    rows += '<div class="incomplete-note">' + esc(T("f_incomplete")) + esc(mf) + "</div>";
  }
  if (w.date) rows += '<div class="row"><b>' + esc(T("f_cast_date")) + "：</b>" + esc(w.date) + "</div>";
  var castList = (w.actresses && w.actresses.length) ? w.actresses : (rec.owner ? [rec.owner] : []);
  if (castList.length) {
    var castHtml = castList.map(function (n) { return '<a href="#/a/' + enc(n) + '">' + esc(actressName(n)) + "</a>"; }).join("、");
    rows += '<div class="row"><b>' + esc(T("f_cast")) + "：</b>" + castHtml + "</div>";
  }
  if (w.maker) rows += '<div class="row"><b>' + esc(T("f_maker")) + "：</b>" + chip("m", w.maker) + "</div>";
  if (w.label) rows += '<div class="row"><b>' + esc(T("f_label")) + "：</b>" + chip("m", w.label) + "</div>";
  if (w.series) rows += '<div class="row"><b>' + esc(T("f_series")) + "：</b>" + chip("s", w.series) + "</div>";
  if (w.duration) rows += '<div class="row"><b>' + esc(T("f_duration")) + "：</b>" + esc(w.duration) + " " + (getLang() === "zh" ? "分钟" : "分") + "</div>";
  if (w.director) rows += '<div class="row"><b>' + esc(T("f_director")) + "：</b>" + chip("d", w.director) + "</div>";
  if (w.rating) rows += '<div class="row"><b>' + esc(T("f_rating")) + "：</b>★ " + esc(w.rating) + (w.rating_count ? "（" + w.rating_count + (getLang() === "zh" ? " 评价" : " 評価") + "）" : "") + "</div>";

  var tagList = (w.labels || []).concat(w.tags || []);
  var tagHtml = chips("t", tagList);
  var ext = buildExtButtons(w);

  return (
    '<div class="crumb"><a href="#/">' + esc(T("brand")) + '</a><span class="sep">/</span>' +
      '<a href="#/a/' + enc(rec.owner || "") + '">' + esc(actressName(rec.owner || "未知")) + '</a><span class="sep">/</span><b>' + esc(w.code) + "</b></div>" +
    '<div class="detail">' +
      '<div class="poster">' + imgTag(w.cover, w.code) + (w.cover ? "" : esc(w.code)) + "</div>" +
      "<div class=\"dinfo\"><h1>" + (workTitle(w) ? esc(workTitle(w)) : esc(w.code)) + "</h1>" +
        '<div class="code">' + esc(w.code) + "</div>" + rows +
        (tagHtml ? '<div class="tags">' + tagHtml + "</div>" : "") +
        (ext ? '<div class="extwrap">' + ext + "</div>" : "") +
      "</div></div>" +
    (w.synopsis ? '<section class="block"><div class="block-head"><h2>' + esc(T("f_synopsis")) + '</h2></div><p class="synopsis">' + esc(w.synopsis) + "</p></section>" : "")
  );
}

/* ============================ 统计总览 ============================ */
export function stats() {
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

  function topMap(obj, n) { return Object.keys(obj).sort(function (a, b) { return obj[b] - obj[a]; }).slice(0, n); }
  function barRow(k, v, max) {
    var pct = max ? Math.round(v / max * 100) : 0;
    return '<div class="bar-row"><span class="bar-lbl">' + esc(k) + '</span>' +
      '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
      '<span class="bar-val">' + v + "</span></div>";
  }
  var topMakers = topMap(makers, 15), topTags = topMap(tags, 24), topDirectors = topMap(directors, 10);
  var actressRank = DB_actresses().slice().sort(function (a, b) { return (b.work_count || 0) - (a.work_count || 0); }).slice(0, 15);

  return (
    '<section class="hero"><h1>' + esc(T("stats_title")) + '</h1><p class="lead">' +
      esc(T("stats_lead")(actressCount(), workCount(), yMin, yMax)) + "</p></section>" +
    '<section class="stats-grid">' +
      '<div class="stat-card"><div class="num">' + actressCount() + '</div><div class="lbl">' + esc(T("s_actresses")) + "</div></div>" +
      '<div class="stat-card"><div class="num">' + workCount() + '</div><div class="lbl">' + esc(T("s_works")) + "</div></div>" +
      '<div class="stat-card"><div class="num">' + rated + '</div><div class="lbl">' + esc(T("s_rated")) + "</div></div>" +
      '<div class="stat-card"><div class="num">' + (rated ? (ratingSum / rated).toFixed(1) : "—") + '</div><div class="lbl">' + esc(T("s_avg")) + "</div></div>" +
    "</section>" +
    '<section class="block"><div class="block-head"><h2>' + esc(T("s_year")) + "</h2></div>" +
      '<div class="bars">' + yearKeys.map(function (k) { return barRow(k, years[k], yMaxCount); }).join("") + "</div></section>" +
    '<section class="block"><div class="block-head"><h2>' + esc(T("s_maker")) + '</h2></div><ol class="rank">' +
      topMakers.map(function (m) { return '<li><a href="#/m/' + enc(m) + '">' + esc(m) + '</a><span class="rc">' + makers[m] + "</span></li>"; }).join("") + "</ol></section>" +
    '<section class="block"><div class="block-head"><h2>' + esc(T("s_tag")) + '</h2></div><div class="chipcloud">' +
      topTags.map(function (t) { return chip("t", t); }).join("") + "</div></section>" +
    '<section class="block"><div class="block-head"><h2>' + esc(T("s_actress_rank")) + '</h2></div><ol class="rank">' +
      actressRank.map(function (a) { return '<li><a href="#/a/' + enc(a.name) + '">' + esc(actressName(a.name)) + '</a><span class="rc">' + (a.work_count || 0) + "</span></li>"; }).join("") + "</ol></section>" +
    (topDirectors.length ? '<section class="block"><div class="block-head"><h2>' + esc(T("s_director")) + '</h2></div><ol class="rank">' +
      topDirectors.map(function (d) { return '<li><a href="#/d/' + enc(d) + '">' + esc(d) + '</a><span class="rc">' + directors[d] + "</span></li>"; }).join("") + "</ol></section>" : "")
  );
}
