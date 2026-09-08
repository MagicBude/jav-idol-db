// main.js — 应用入口
//
// ┌─ 架构（分层，无构建步骤：纯 ES modules 直接由静态托管运行）─────────────────┐
// │  core/        纯逻辑层（无 DOM 依赖，可独立单测）                          │
// │    util.js    纯函数：HTML 转义 / <img> / hash 编解码 / 数字容错          │
// │    state.js   集中状态：LANG · VIEW_MODE · THEME · HOVER_SRC（持久化 + 订阅）│
// │    data.js    数据访问层：读 window.JAV_DB，扁平化作品 + 查询/分组助手      │
// │    i18n.js    多语言文案 + 显示名（随语言切换）                            │
// │    sources.js 作品外部来源链接（查看/搜索入口，含悬停角标样式）            │
// │  components/  视图组件（每个函数返回 HTML 字符串）                        │
// │    cards.js   作品卡 / 女优卡 / 标签 chip / 预览图                        │
// │    toolbar.js 作品工具条（分组 + 视图切换 + 排序）                        │
// │    layout.js  持久化外壳：顶部导航栏 + 筛选弹窗                            │
// │    views.js   各路由页面（首页/女优/筛选/搜索/详情/统计/分组/组合筛选）    │
// │  router.js    hash 路由：主段 + 查询串分发到 views.*，渲染到 #app         │
// │  main.js      入口：挂载外壳 + 绑定 + 路由 + 状态订阅                      │
// └────────────────────────────────────────────────────────────────────────┘
//
// 数据流：scripts/build_index.py → window.JAV_DB → core/data.js(取数) → components/*(视图) → #app
// 状态流：用户操作 → core/state.js(setX) → notify → 订阅者(main.js)做最小重渲染
//   · lang    变更：整页重渲染（显示名切换）   · theme 变更：仅刷新外壳图标
//   · view    变更：仅切换 .grid--work 形态       · hoversrc 变更：仅重渲染作品网格
import { mountChrome, paintChrome } from "./components/layout.js";
import { route } from "./router.js";
import { subscribe, getViewMode, setViewMode } from "./core/state.js";
import { renderGrid, viewState } from "./components/views.js";

// 视图模式仅作用于「作品网格」，女优网格（grid--actress）不受影响
function paintViewMode() {
  var vm = getViewMode();
  var grids = document.querySelectorAll(".grid--work");
  for (var i = 0; i < grids.length; i++) grids[i].className = "grid grid--work grid--" + vm;
  var btns = document.querySelectorAll(".viewbtn");
  for (var j = 0; j < btns.length; j++) {
    var m = btns[j].getAttribute("data-mode");
    btns[j].classList.toggle("active", m === vm);
    btns[j].setAttribute("aria-pressed", m === vm ? "true" : "false");
  }
}

// 重渲染 #gridwrap（排序 / 分组变更时复用当前列表）
function repaintGrid() {
  var wrap = document.getElementById("gridwrap");
  if (!wrap) return;
  wrap.innerHTML = renderGrid(viewState.recs, viewState.sort, viewState.groupBy || "none");
}

// 排序下拉：仅重渲染 #gridwrap，保留当前视图与滚动位置
function bindSort() {
  document.addEventListener("change", function (e) {
    if (!e.target || e.target.id !== "sortsel") return;
    viewState.sort = e.target.value;
    repaintGrid();
  });
}

// 分组下拉：仅重渲染 #gridwrap
function bindGroups() {
  document.addEventListener("change", function (e) {
    if (!e.target || e.target.id !== "groupsel") return;
    viewState.groupBy = e.target.value;
    repaintGrid();
  });
}

// 视图切换按钮（事件委托）
function bindViewButtons() {
  document.addEventListener("click", function (e) {
    var b = e.target.closest ? e.target.closest(".viewbtn") : null;
    if (b) setViewMode(b.getAttribute("data-mode"));
  });
}

// 卡片悬停来源角标点击：用 <span> 代替嵌套 <a>，这里处理新标签页打开
function bindSrcChips() {
  document.addEventListener("click", function (e) {
    var chip = e.target.closest ? e.target.closest(".src-chip") : null;
    if (!chip) return;
    var href = chip.getAttribute("data-href");
    if (href) window.open(href, "_blank", "noopener,noreferrer");
    e.stopPropagation();
    e.preventDefault();
  });
}

// 状态变更广播
subscribe(function (evt) {
  if (evt.type === "lang") { route({ scroll: false }); }       // 重渲染整页以切换显示名
  else if (evt.type === "theme") { paintChrome(); }            // 仅刷新外壳图标
  else if (evt.type === "view") { paintViewMode(); }           // 轻量切换网格形态
  else if (evt.type === "hoversrc") { repaintGrid(); paintChrome(); } // 重渲染作品网格以增减悬停层
});

function boot() {
  mountChrome();
  bindSort();
  bindGroups();
  bindViewButtons();
  bindSrcChips();
  window.addEventListener("hashchange", route);
  route();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
