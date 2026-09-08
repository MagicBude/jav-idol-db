// components/layout.js — 持久化外壳：左侧栏（品牌 + 分类导航）+ 顶部栏（搜索 + 主题）
// mountChrome() 仅执行一次构建 DOM；paintChrome() 在路由/语言/主题变化时刷新动态部分。

import { T } from "../core/i18n.js";
import { getLang, getTheme, setLang, setTheme } from "../core/state.js";

// 导航项：route 用于高亮匹配，icon 为装饰
var NAV = [
  { group: "nav_discover", items: [
    { route: "#/", icon: "🏠", key: "nav_home" },
    { route: "#/q/", icon: "🎞", key: "nav_works" },
    { route: "#/actresses", icon: "👤", key: "nav_actresses" }
  ]},
  { group: "nav_library", items: [
    { route: "#/tags", icon: "🏷", key: "nav_tags" },
    { route: "#/makers", icon: "🏭", key: "nav_makers" },
    { route: "#/series", icon: "📚", key: "nav_series" },
    { route: "#/directors", icon: "🎬", key: "nav_directors" },
    { route: "#/stats", icon: "📊", key: "nav_stats" }
  ]}
];

// 当前 hash 的「主段」用于高亮
function activeRoute() {
  var h = (location.hash || "#/").slice(1);
  var main = (h.split("/").filter(Boolean)[0] || "");
  if (main === "" || main === "/") return "#/";
  if (main === "q") return "#/q/";
  if (main === "a") return "#/actresses";
  if (main === "t") return "#/tags";
  if (main === "m") return "#/makers";
  if (main === "s") return "#/series";
  if (main === "d") return "#/directors";
  if (main === "stats") return "#/stats";
  return null;
}

function buildNavHtml() {
  var html = "";
  for (var gi = 0; gi < NAV.length; gi++) {
    var g = NAV[gi];
    html += '<div class="nav-label">' + esc(T(g.group)) + "</div><nav class=\"nav\">";
    for (var ii = 0; ii < g.items.length; ii++) {
      var it = g.items[ii];
      html += '<a href="' + it.route + '" data-nav="' + it.route + '">' +
        '<span class="ico">' + it.icon + "</span><span>" + esc(T(it.key)) + "</span></a>";
    }
    html += "</nav>";
  }
  return html;
}

export function mountChrome() {
  var sidebar = document.getElementById("sidebar");
  var topbar = document.getElementById("topbar");
  if (!sidebar || !topbar) return;

  sidebar.innerHTML =
    '<div class="brand"><div class="logo">ID</div>' +
      '<div><div class="name">' + esc(T("brand")) + '</div>' +
      '<div class="sub">' + esc(T("brand_sub")) + "</div></div></div>" +
    buildNavHtml() +
    '<div class="sidebar-foot">' +
      '<button class="seg" data-lang="ja" id="lang-ja">JA</button>' +
      '<button class="seg" data-lang="zh" id="lang-zh">中文</button>' +
    "</div>";

  topbar.innerHTML =
    '<button class="icon-btn hamburger" id="hamburger" aria-label="menu">&#9776;</button>' +
    '<div class="brand-mini"><span class="logo" style="width:30px;height:30px;font-size:13px;border-radius:9px;' +
      'background:linear-gradient(135deg,var(--accent),#9b8bff);color:#fff;display:grid;place-items:center;' +
      'font-weight:800">ID</span></div>' +
    '<div class="search"><span class="ico">&#128269;</span>' +
      '<input id="search" type="search" autocomplete="off" placeholder="' + esc(T("search_ph")) + '"></div>' +
    '<button class="icon-btn" id="themebtn" aria-label="theme">&#9788;</button>';

  bindChrome();
  paintChrome();
}

function bindChrome() {
  var lja = document.getElementById("lang-ja");
  var lzh = document.getElementById("lang-zh");
  if (lja) lja.addEventListener("click", function () { setLang("ja"); });
  if (lzh) lzh.addEventListener("click", function () { setLang("zh"); });
  var tb = document.getElementById("themebtn");
  if (tb) tb.addEventListener("click", function () { setTheme(getTheme() === "dark" ? "light" : "dark"); });
  var ham = document.getElementById("hamburger");
  if (ham) ham.addEventListener("click", function () { document.body.classList.toggle("nav-open"); });
  var scrim = document.getElementById("scrim");
  if (scrim) scrim.addEventListener("click", function () { document.body.classList.remove("nav-open"); });
  var box = document.getElementById("search");
  if (box) box.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      var v = box.value.trim();
      location.hash = v ? "#/q/" + encodeURIComponent(v) : "#/q/";
      document.body.classList.remove("nav-open");
    }
  });
}

/** 刷新外壳动态部分：高亮导航、语言段、主题图标、搜索占位 */
export function paintChrome() {
  var lang = getLang();
  var theme = getTheme();

  var act = activeRoute();
  var links = document.querySelectorAll("#sidebar .nav a");
  for (var i = 0; i < links.length; i++) {
    var el = links[i];
    el.classList.toggle("active", el.getAttribute("data-nav") === act);
  }
  var lja = document.getElementById("lang-ja"), lzh = document.getElementById("lang-zh");
  if (lja) lja.classList.toggle("active", lang === "ja");
  if (lzh) lzh.classList.toggle("active", lang === "zh");
  var tb = document.getElementById("themebtn");
  if (tb) tb.textContent = (theme === "dark") ? "☀" : "☾";
  var sb = document.getElementById("search");
  if (sb) sb.placeholder = T("search_ph");
}

// 局部转义（避免额外 import 环路；本模块仅用于导航文本）
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;");
}
