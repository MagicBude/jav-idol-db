// main.js — 入口：挂载外壳、路由、全局事件委托
import { mountChrome, paintChrome } from "./components/layout.js";
import { route } from "./router.js";
import { subscribe, getViewMode, setViewMode } from "./core/state.js";
import { workGrid } from "./components/cards.js";
import { SORTERS } from "./components/toolbar.js";
import { viewState } from "./components/views.js";

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

// 排序下拉：仅重渲染 #gridwrap，保留当前视图与滚动位置
function bindSort() {
  document.addEventListener("change", function (e) {
    if (!e.target || e.target.id !== "sortsel") return;
    var wrap = document.getElementById("gridwrap");
    if (!wrap) return;
    viewState.sort = e.target.value;
    var sorted = viewState.recs.slice().sort(SORTERS[viewState.sort] || SORTERS.date_desc);
    wrap.innerHTML = workGrid(sorted);
  });
}

// 视图切换按钮（事件委托）
function bindViewButtons() {
  document.addEventListener("click", function (e) {
    var b = e.target.closest ? e.target.closest(".viewbtn") : null;
    if (b) setViewMode(b.getAttribute("data-mode"));
  });
}

// 状态变更广播
subscribe(function (evt) {
  if (evt.type === "lang") { route({ scroll: false }); }       // 重渲染整页以切换显示名
  else if (evt.type === "theme") { paintChrome(); }            // 仅刷新图标
  else if (evt.type === "view") { paintViewMode(); }           // 轻量切换网格形态
});

function boot() {
  mountChrome();
  bindSort();
  bindViewButtons();
  window.addEventListener("hashchange", route);
  route();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
