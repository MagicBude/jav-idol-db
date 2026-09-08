// core/sources.js — 作品外部来源链接
// 这些只是「查看 / 搜索」入口，不表示本站认同其内容或可用性。
// 域名可能变动，改这里即可，无需重跑 build_index。
// icon / color 仅用于未来可能的图标层；当前详情页以文字按钮列出。

import { T } from "./i18n.js";
import { getLang } from "./state.js";
import { enc } from "./util.js";

export var SOURCE_LINKS = [
  { key: "javlibrary",  labels: { ja: "javlibrary で見る", zh: "在 javlibrary 查看" },
    url: function (c) { return "https://www.javlibrary.com/cn/vl_searchbyid.php?keyword=" + enc(c.toUpperCase()); } },
  { key: "javbus",      labels: { ja: "javbus で見る", zh: "在 javbus 查看" },
    url: function (c) { return "https://www.javbus.com/" + c.toUpperCase(); } },
  { key: "javdb",       labels: { ja: "javdb で検索", zh: "在 javdb 搜索" },
    url: function (c) { return "https://javdb.com/search?q=" + enc(c.toLowerCase()) + "&f=all"; } },
  { key: "javmenu",     labels: { ja: "javmenu で見る", zh: "在 javmenu 查看" },
    url: function (c) { return "https://javmenu.com/" + enc(c.toUpperCase()); } },
  { key: "missav",      labels: { ja: "missav で見る", zh: "在 missav 查看" },
    url: function (c) { return "https://missav.ws/" + enc(c.toUpperCase()); } },
  { key: "codeav",      labels: { ja: "codeav で見る", zh: "在 codeav 查看" },
    url: function (c) { return "https://www.codeav.net/movie/" + c.toLowerCase(); } },
  { key: "javdatabase", labels: { ja: "javdatabase で見る", zh: "在 javdatabase 查看" },
    url: function (c) { return "https://www.javdatabase.com/movies/" + c.toLowerCase() + "/"; } },
  { key: "minnanoav",   labels: { ja: "みんなのAV で検索", zh: "在 minnanoav 搜索" },
    url: function (c) { return "https://www.minnano-av.com/search_result.php?search_word=" + enc(c.toUpperCase()); } },
  { key: "avsox",       labels: { ja: "avsox で検索", zh: "在 avsox 搜索" },
    url: function (c) { return "https://avsox.click/cn/search/" + enc(c.toLowerCase()); } }
];

/**
 * 构建作品详情页的「外部来源」按钮串（去重合并）：
 * 手工链接 > 预告片 > 数据源 > DMM > 各来源模板。
 * 返回 HTML 字符串（可能为空）。
 */
export function buildExtButtons(w) {
  if (!w) return "";
  var lang = getLang();
  var seen = {};
  var html = "";
  function add(label, href) {
    if (!href || seen[href]) return;
    seen[href] = 1;
    html += '<a class="extbtn" href="' + esc(href) + '" target="_blank" rel="noopener">' + esc(label) + " ↗</a>";
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  if (w.external_links) {
    var links = w.external_links;
    if (typeof links === "string") links = { "链接": links };
    Object.keys(links).forEach(function (k) { add(k, links[k]); });
  }
  if (w.trailer) add("观看预告片 ▶", w.trailer);
  if (w.source_url) {
    var srcLabel = w.source
      ? (lang === "zh" ? "在 " + w.source + " 查看" : w.source + " で見る")
      : (lang === "zh" ? "数据源" : "データソース");
    add(srcLabel, w.source_url);
  }
  if (w.code) {
    add(lang === "zh" ? "在 DMM 搜索" : "DMM で検索", "https://www.dmm.co.jp/search/=/searchstr=" + enc(w.code));
    SOURCE_LINKS.forEach(function (s) { add(s.labels[lang] || s.labels.zh, s.url(w.code)); });
  }
  return html;
}
