// components/layout.js — 持久化外壳：顶部导航栏（品牌 + 分类 Tab + 搜索 + 筛选 + 主题/语言）
// 无侧栏设计（参考 JavBoss 的紧凑 TopBar）：导航为横向 Tab，移动端折叠为汉堡下拉。
// mountChrome() 仅执行一次构建 DOM；paintChrome() 在路由/语言/主题/悬停开关变化时刷新动态部分。

import { T } from "../core/i18n.js";
import { getLang, getTheme, setLang, setTheme, getHoverSrc, setHoverSrc } from "../core/state.js";
import { enc } from "../core/util.js";

// 顶部导航 Tab：route 用于高亮匹配，key 为文案
var NAV = [
  { route: "#/", key: "nav_home" },
  { route: "#/q/", key: "nav_works" },
  { route: "#/actresses", key: "nav_actresses" },
  { route: "#/tags", key: "nav_tags" },
  { route: "#/makers", key: "nav_makers" },
  { route: "#/series", key: "nav_series" },
  { route: "#/directors", key: "nav_directors" },
  { route: "#/agencies", key: "nav_agencies" },
  { route: "#/stats", key: "nav_stats" }
];

// 当前 hash 的「主段」对应的高亮 Tab
function activeRoute() {
  var h = (location.hash || "#/").slice(1);
  var main = (h.split("/").filter(Boolean)[0] || "");
  if (main === "" || main === "home") return "#/";
  if (main === "q" || main === "w" || main === "filter") return "#/q/";
  if (main === "a") return "#/actresses";
  if (main === "t") return "#/tags";
  if (main === "m") return "#/makers";
  if (main === "s") return "#/series";
  if (main === "d") return "#/directors";
  if (main === "agencies" || main === "agency") return "#/agencies";
  if (main === "stats") return "#/stats";
  return null;
}

export function mountChrome() {
  var topbar = document.getElementById("topbar");
  if (!topbar) return;

  var tabs = NAV.map(function (it) {
    return '<a href="' + it.route + '" data-nav="' + it.route + '" data-key="' + esc(it.key) + '" class="tab">' + esc(T(it.key)) + "</a>";
  }).join("");

  topbar.innerHTML =
    '<a class="brand" href="#/" aria-label="home">' +
      '<span class="logo">ID</span><span class="brand-name">' + esc(T("brand")) + "</span></a>" +
    '<button class="icon-btn hamburger" id="hamburger" aria-label="menu" aria-expanded="false">&#9776;</button>' +
    '<nav class="topnav" id="topnav">' + tabs + "</nav>" +
    '<div class="spacer"></div>' +
    '<div class="search"><span class="ico">&#128269;</span>' +
      '<input id="search" type="search" autocomplete="off" placeholder="' + esc(T("search_ph")) + '"></div>' +
    '<button class="icon-btn" id="filterbtn" aria-label="' + esc(T("open_filter")) + '" title="' + esc(T("open_filter")) + '">&#9776;&#65049;</button>' +
    '<button class="icon-btn" id="srcbtn" aria-label="' + esc(T("hover_src")) + '" title="' + esc(T("hover_src")) + '">&#128279;</button>' +
    '<button class="icon-btn" id="themebtn" aria-label="theme" title="theme">&#9788;</button>' +
    '<div class="langseg" role="group" aria-label="language">' +
      '<button class="seg" data-lang="ja" id="lang-ja">JA</button>' +
      '<button class="seg" data-lang="zh" id="lang-zh">中</button>' +
    "</div>";

  mountFilterModal();
  bindChrome();
  paintChrome();
}

/* ---------------- 筛选弹窗 ---------------- */
function mountFilterModal() {
  var existing = document.getElementById("filtermodal");
  if (existing) return;
  var scrim = document.createElement("div");
  scrim.className = "modal-scrim";
  scrim.id = "filtermodal";
  scrim.innerHTML =
    '<div class="modal" role="dialog" aria-modal="true" aria-label="' + esc(T("filter_title")) + '">' +
      '<div class="modal-head"><h3>' + esc(T("filter_title")) + '</h3>' +
        '<button class="icon-btn modal-x" id="filterx" aria-label="close">&#10005;</button></div>' +
      '<div class="modal-body">' +
        '<label class="fld"><span>' + esc(T("filter_keyword")) + '</span><input id="f_q" type="text" autocomplete="off"></label>' +
        '<label class="fld"><span>' + esc(T("filter_actress")) + '</span><input id="f_actress" type="text" autocomplete="off"></label>' +
        '<label class="fld"><span>' + esc(T("filter_tag")) + '</span><input id="f_tag" type="text" autocomplete="off"></label>' +
        '<label class="fld"><span>' + esc(T("filter_maker")) + '</span><input id="f_maker" type="text" autocomplete="off"></label>' +
        '<label class="fld"><span>' + esc(T("filter_series")) + '</span><input id="f_series" type="text" autocomplete="off"></label>' +
      "</div>" +
      '<div class="modal-foot">' +
        '<button class="btn ghost" id="filterreset">' + esc(T("filter_reset")) + "</button>" +
        '<button class="btn primary" id="filterapply">' + esc(T("filter_apply")) + "</button>" +
      "</div>" +
    "</div>";
  document.body.appendChild(scrim);
}

export function openFilter(prefill) {
  prefill = prefill || {};
  var m = document.getElementById("filtermodal");
  if (!m) return;
  var set = function (id, v) { var el = document.getElementById(id); if (el) el.value = v || ""; };
  set("f_q", prefill.q); set("f_actress", prefill.actress); set("f_tag", prefill.tag);
  set("f_maker", prefill.maker); set("f_series", prefill.series);
  m.classList.add("open");
}
export function closeFilter() {
  var m = document.getElementById("filtermodal");
  if (m) m.classList.remove("open");
}

function bindChrome() {
  var lja = document.getElementById("lang-ja"), lzh = document.getElementById("lang-zh");
  if (lja) lja.addEventListener("click", function () { setLang("ja"); });
  if (lzh) lzh.addEventListener("click", function () { setLang("zh"); });

  var tb = document.getElementById("themebtn");
  if (tb) tb.addEventListener("click", function () { setTheme(getTheme() === "dark" ? "light" : "dark"); });

  var sb = document.getElementById("srcbtn");
  if (sb) sb.addEventListener("click", function () { setHoverSrc(!getHoverSrc()); });

  var ham = document.getElementById("hamburger");
  if (ham) ham.addEventListener("click", function () {
    var nav = document.getElementById("topnav");
    if (nav) {
      var open = nav.classList.toggle("open");
      ham.setAttribute("aria-expanded", open ? "true" : "false");
    }
  });

  var box = document.getElementById("search");
  if (box) box.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      var v = box.value.trim();
      location.hash = v ? "#/q/" + enc(v) : "#/q/";
    }
  });

  // 筛选弹窗交互
  var fbtn = document.getElementById("filterbtn");
  if (fbtn) fbtn.addEventListener("click", function () {
    var p = parseFilterHash();
    openFilter(p);
  });
  var fx = document.getElementById("filterx");
  if (fx) fx.addEventListener("click", closeFilter);
  var freset = document.getElementById("filterreset");
  if (freset) freset.addEventListener("click", function () {
    ["f_q", "f_actress", "f_tag", "f_maker", "f_series"].forEach(function (id) {
      var el = document.getElementById(id); if (el) el.value = "";
    });
  });
  var fapply = document.getElementById("filterapply");
  if (fapply) fapply.addEventListener("click", function () {
    var q = val("f_q"), actress = val("f_actress"), tag = val("f_tag"), maker = val("f_maker"), series = val("f_series");
    var qs = [];
    if (q) qs.push("q=" + enc(q));
    if (actress) qs.push("actress=" + enc(actress));
    if (tag) qs.push("tag=" + enc(tag));
    if (maker) qs.push("maker=" + enc(maker));
    if (series) qs.push("series=" + enc(series));
    closeFilter();
    location.hash = "#/filter" + (qs.length ? "?" + qs.join("&") : "");
  });
  var fmodal = document.getElementById("filtermodal");
  if (fmodal) {
    fmodal.addEventListener("click", function (e) { if (e.target === fmodal) closeFilter(); });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeFilter();
      var nav = document.getElementById("topnav");
      if (nav) { nav.classList.remove("open"); var h = document.getElementById("hamburger"); if (h) h.setAttribute("aria-expanded", "false"); }
    }
  });
}

function val(id) { var el = document.getElementById(id); return el ? el.value.trim() : ""; }

/** 解析当前 #/filter?... 的查询参数（供弹窗预填） */
export function parseFilterHash() {
  var h = (location.hash || "").slice(1);
  var qi = h.indexOf("?");
  if (qi < 0) return {};
  var sp = new URLSearchParams(h.slice(qi + 1));
  var out = {};
  ["q", "actress", "tag", "maker", "series"].forEach(function (k) { if (sp.get(k)) out[k] = sp.get(k); });
  return out;
}

/** 刷新外壳动态部分：高亮 Tab、语言段、主题图标、悬停来源开关、搜索占位、收起移动端导航 */
export function paintChrome() {
  var lang = getLang();
  var theme = getTheme();

  var act = activeRoute();
  var links = document.querySelectorAll("#topnav .tab");
  for (var i = 0; i < links.length; i++) {
    links[i].classList.toggle("active", links[i].getAttribute("data-nav") === act);
    var k = links[i].getAttribute("data-key");
    if (k) links[i].textContent = T(k);   // 语言切换时同步更新 Tab 文案
  }
  var lja = document.getElementById("lang-ja"), lzh = document.getElementById("lang-zh");
  if (lja) lja.classList.toggle("active", lang === "ja");
  if (lzh) lzh.classList.toggle("active", lang === "zh");
  var tb = document.getElementById("themebtn");
  if (tb) tb.textContent = (theme === "dark") ? "☀" : "☾";
  var sb = document.getElementById("srcbtn");
  if (sb) sb.classList.toggle("active", getHoverSrc());
  var sbox = document.getElementById("search");
  if (sbox) sbox.placeholder = T("search_ph");

  var nav = document.getElementById("topnav");
  if (nav) nav.classList.remove("open");
  var ham = document.getElementById("hamburger");
  if (ham) ham.setAttribute("aria-expanded", "false");
}

// 局部转义
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;");
}
