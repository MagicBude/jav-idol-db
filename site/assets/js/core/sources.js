// core/sources.js — 作品外部来源链接
// 这些只是「查看 / 搜索」入口，不表示本站认同其内容或可用性。
// 域名可能变动，改这里即可，无需重跑 build_index。
// 每个来源带 short(角标文字) / color(角标底色)，供作品卡悬停图标层复用。

import { T } from "./i18n.js";
import { getLang } from "./state.js";
import { enc } from "./util.js";

export var SOURCE_LINKS = [
  { key: "javlibrary",  short: "JL", color: "#d9354e",
    labels: { ja: "javlibrary で見る", zh: "在 javlibrary 查看" },
    url: function (c) { return "https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=" + enc(c.toUpperCase()); } },
  { key: "javbus",      short: "JB", color: "#2d9cdb",
    labels: { ja: "javbus で見る", zh: "在 javbus 查看" },
    url: function (c) { return "https://www.javbus.com/" + c.toUpperCase(); } },
  { key: "javdb",       short: "JD", color: "#8b5cf6",
    labels: { ja: "javdb で検索", zh: "在 javdb 搜索" },
    url: function (c) { return "https://javdb.com/search?q=" + enc(c.toLowerCase()) + "&f=all"; } },
  { key: "javmenu",     short: "JM", color: "#1aa179",
    labels: { ja: "javmenu で見る", zh: "在 javmenu 查看" },
    url: function (c) { return "https://javmenu.com/" + enc(c.toUpperCase()); } },
  { key: "missav",      short: "MA", color: "#ef4444",
    labels: { ja: "missav で見る", zh: "在 missav 查看" },
    url: function (c) { return "https://missav.ws/" + enc(c.toUpperCase()); } },
  { key: "codeav",      short: "CA", color: "#3b82f6",
    labels: { ja: "codeav で見る", zh: "在 codeav 查看" },
    url: function (c) { return "https://www.codeav.net/movie/" + c.toLowerCase(); } },
  { key: "javdatabase", short: "DB", color: "#0ea5e9",
    labels: { ja: "javdatabase で見る", zh: "在 javdatabase 查看" },
    url: function (c) { return "https://www.javdatabase.com/movies/" + c.toLowerCase() + "/"; } },
  { key: "minnanoav",   short: "MN", color: "#db2777",
    labels: { ja: "みんなのAV で検索", zh: "在 minnanoav 搜索" },
    url: function (c) { return "https://www.minnano-av.com/search_result.php?search_word=" + enc(c.toUpperCase()); } },
  { key: "avsox",       short: "AX", color: "#f97316",
    labels: { ja: "avsox で検索", zh: "在 avsox 搜索" },
    url: function (c) { return "https://avsox.click/cn/search/" + enc(c.toLowerCase()); } }
];

// 特殊入口（非 SOURCE_LINKS）的角标样式
var EXTRA_META = {
  dmm:     { short: "DM", color: "#e60012" },
  trailer: { short: "▶", color: "#111827" },
  custom:  { short: "↗", color: "#475569" }
};

/** 角标文字 / 底色：SOURCE_LINKS 优先，其次特殊入口，缺省中性灰 */
function chipMeta(key) {
  for (var i = 0; i < SOURCE_LINKS.length; i++) {
    if (SOURCE_LINKS[i].key === key) return { short: SOURCE_LINKS[i].short, color: SOURCE_LINKS[i].color };
  }
  if (EXTRA_META[key]) return EXTRA_META[key];
  return { short: "↗", color: "#475569" };
}

/**
 * 收集某作品的全部外部来源入口（去重合并），按优先级排序：
 * 手工链接 > 预告片 > 数据源 > DMM > 各来源模板。
 * 返回 [{ key, label, href }]。
 */
export function collectSources(w) {
  if (!w) return [];
  var lang = getLang();
  var seen = {};
  var out = [];
  function add(key, label, href) {
    if (!href || seen[href]) return;
    seen[href] = 1;
    out.push({ key: key, label: label, href: href });
  }
  if (w.external_links) {
    var links = w.external_links;
    if (typeof links === "string") links = { "链接": links };
    Object.keys(links).forEach(function (k) { add("custom", k, links[k]); });
  }
  if (w.trailer) add("trailer", lang === "zh" ? "观看预告片" : "予告を見る", w.trailer);
  if (w.source_url) {
    var srcLabel = w.source
      ? (lang === "zh" ? "在 " + w.source + " 查看" : w.source + " で見る")
      : (lang === "zh" ? "数据源" : "データソース");
    add("source", srcLabel, w.source_url);
  }
  if (w.code) {
    add("dmm", lang === "zh" ? "在 DMM 搜索" : "DMM で検索", "https://www.dmm.co.jp/search/=/searchstr=" + enc(w.code));
    SOURCE_LINKS.forEach(function (s) { add(s.key, s.labels[lang] || s.labels.zh, s.url(w.code)); });
  }
  return out;
}

/**
 * 详情页「外部来源」文字按钮串（去重合并）。
 * 返回 HTML 字符串（可能为空）。
 */
export function buildExtButtons(w) {
  var list = collectSources(w);
  if (!list.length) return "";
  return list.map(function (e) {
    return '<a class="extbtn" href="' + esc(e.href) + '" target="_blank" rel="noopener">' + esc(e.label) + " ↗</a>";
  }).join("");
}

/**
 * 作品卡悬停图标层：每个来源一个圆形角标（短名 + 品牌色），点击跳转。
 * 返回 HTML 字符串（可能为空）。
 */
export function sourceIconChips(w) {
  var list = collectSources(w);
  if (!list.length) return "";
  return list.map(function (e) {
    var m = chipMeta(e.key);
    // 用 <span> 而非 <a>：卡片本身已是 <a>，嵌套 <a> 会导致浏览器解析时把卡片内容清空。
    return '<span class="src-chip" style="--c:' + m.color + '" data-href="' + esc(e.href) +
      '" title="' + esc(e.label) + '" aria-label="' + esc(e.label) + '">' +
      esc(m.short) + "</span>";
  }).join("");
}

function esc(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
