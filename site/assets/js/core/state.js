// core/state.js — 全局 UI 状态（语言 / 作品视图模式 / 主题）
// 仅持久化到 localStorage，不依赖任何视图层；变更通过监听器广播。

var LANGS = ["ja", "zh"];
var VIEW_MODES = ["poster", "cover", "list"];

function lsGet(k, d) {
  try { var v = localStorage.getItem(k); return v == null ? d : v; }
  catch (e) { return d; }
}
function lsSet(k, v) {
  try { localStorage.setItem(k, v); } catch (e) {}
}

// ---- 语言 ----
var LANG = LANGS.indexOf(lsGet("lang", "ja")) >= 0 ? lsGet("lang", "ja") : "ja";

// ---- 作品视图模式（仅作用于「作品网格」，女优网格独立不受影响）----
var VIEW_MODE = VIEW_MODES.indexOf(lsGet("view", "poster")) >= 0 ? lsGet("view", "poster") : "poster";

// ---- 主题（默认浅色；记忆用户选择，否则跟随系统）----
var THEME = (function () {
  var t = lsGet("theme", null);
  if (t && (t === "light" || t === "dark")) return t;
  try {
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
  } catch (e) {}
  return "light";
})();

// ---- 订阅者（视图层在状态变化时重渲染）----
var listeners = [];
export function subscribe(fn) { listeners.push(fn); }
function notify(evt) { listeners.forEach(function (fn) { fn(evt); }); }

// ---- 访问器 ----
export function getLang() { return LANG; }
export function getViewMode() { return VIEW_MODE; }
export function getTheme() { return THEME; }
export function langList() { return LANGS.slice(); }
export function viewModes() { return VIEW_MODES.slice(); }

// ---- 变更器 ----
export function setLang(l) {
  if (LANGS.indexOf(l) < 0 || l === LANG) return;
  LANG = l; lsSet("lang", l);
  if (document.documentElement) document.documentElement.lang = (l === "zh") ? "zh-CN" : "ja";
  notify({ type: "lang" });
}

export function setViewMode(m) {
  if (VIEW_MODES.indexOf(m) < 0 || m === VIEW_MODE) return;
  VIEW_MODE = m; lsSet("view", m);
  notify({ type: "view" });
}

export function setTheme(t) {
  if ((t !== "light" && t !== "dark") || t === THEME) return;
  THEME = t; lsSet("theme", t);
  applyThemeAttr(t);
  notify({ type: "theme" });
}

/** 把主题写到 <html data-theme>（CSS 据此切换变量） */
export function applyThemeAttr(t) {
  if (document.documentElement) document.documentElement.setAttribute("data-theme", t || "light");
}

// 初次应用主题到 <html data-theme>
applyThemeAttr(THEME);
if (document.documentElement) document.documentElement.lang = (LANG === "zh") ? "zh-CN" : "ja";
