// router.js — hash 路由：解析 #/... 并渲染对应视图到 #app
// 支持 #/filter?q=...&maker=... 形式的查询字符串（组合筛选弹窗）。
import { dec, esc } from "./core/util.js";
import { T } from "./core/i18n.js";
import { paintChrome } from "./components/layout.js";
import * as V from "./components/views.js";

export function route(opts) {
  opts = opts || {};
  var app = document.getElementById("app");
  if (!app) return;

  // 拆分 path 与 query string
  var h = (location.hash || "#/").slice(1);
  var qi = h.indexOf("?");
  var path = qi >= 0 ? h.slice(0, qi) : h;
  var qs = qi >= 0 ? h.slice(qi + 1) : "";
  var sp = new URLSearchParams(qs);

  var parts = path.split("/").filter(Boolean);
  var main = parts[0] || "";
  var param = dec(parts.slice(1).join("/"));

  var html;
  switch (main) {
    case "": case "/": case "home": html = V.home(); break;
    case "a": html = V.actressDetail(param); break;
    case "w": html = V.workDetail(param); break;
    case "t": html = V.filterView("t", param); break;
    case "m": html = V.filterView("m", param); break;
    case "s": html = V.filterView("s", param); break;
    case "d": html = V.filterView("d", param); break;
    case "q": html = V.searchView(param); break;
    case "actresses": html = V.actressList(); break;
    case "agencies": html = V.agencyList(); break;
    case "agency": html = V.actressByAgency(param); break;
    case "tags": html = V.browseFacet("tags"); break;
    case "makers": html = V.browseFacet("makers"); break;
    case "series": html = V.browseFacet("series"); break;
    case "directors": html = V.browseFacet("directors"); break;
    case "stats": html = V.stats(); break;
    case "filter": {
      var params = {};
      ["q", "actress", "tag", "maker", "series"].forEach(function (k) { if (sp.get(k)) params[k] = sp.get(k); });
      html = V.combinedFilterView(params);
      break;
    }
    default: html = '<div class="empty">' + esc(T("err_page")) + esc(h) + "</div>";
  }

  app.innerHTML = html;
  // 视图切换淡入：每次重渲染先移除再强制重排后加回 .in，重新触发动画
  app.classList.remove("in"); void app.offsetWidth; app.classList.add("in");
  paintChrome();
  if (opts.scroll !== false) window.scrollTo(0, 0);
}
