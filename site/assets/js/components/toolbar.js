// components/toolbar.js — 上下文工具条（作品视图切换 + 排序 + 分组）
// 仅「作品类」视图（首页最新 / 作品列表 / 搜索 / 筛选 / 女优详情的作品区）使用；
// 女优总览网格与统计页不使用视图切换。

import { T } from "../core/i18n.js";
import { getViewMode, viewModes } from "../core/state.js";

var SORT_OPTS = [
  ["date_desc", "s_date_desc"], ["date_asc", "s_date_asc"],
  ["rating_desc", "s_rating_desc"], ["duration_desc", "s_duration_desc"], ["code_asc", "s_code_asc"]
];

// 分组维度（作品内联分组页；none = 不分组成单一网格）
export var GROUP_OPTS = [
  ["none", "g_none"], ["year", "g_year"], ["maker", "g_maker"]
];

/**
 * @param opts { count, showView, showSort, sortValue, groupBy }
 *   showView: 是否显示 海报墙/封面/列表 切换
 *   showSort: 是否显示排序下拉
 *   groupBy:  当前分组 key（none/year/maker），null 表示不显示分组控件
 */
export function toolbar(opts) {
  opts = opts || {};
  var parts = [];
  if (opts.count != null) {
    parts.push('<span class="count">' + opts.count + " " + T("f_works") + "</span>");
  }
  parts.push('<span class="grow"></span>');
  if (opts.groupBy !== null && opts.groupBy !== undefined) {
    var gsel = '<label class="sortsel-wrap"><span class="sortsel-label">' + T("group_by") + "</span>" +
      '<select id="groupsel" class="sortsel">';
    GROUP_OPTS.forEach(function (o) {
      gsel += '<option value="' + o[0] + '"' + (o[0] === opts.groupBy ? " selected" : "") + ">" + T(o[1]) + "</option>";
    });
    gsel += "</select></label>";
    parts.push(gsel);
  }
  if (opts.showView) {
    var vm = getViewMode();
    var seg = '<div class="viewseg" role="group" aria-label="view">';
    viewModes().forEach(function (m) {
      var label = T("v_" + m);
      seg += '<button type="button" class="viewbtn' + (m === vm ? " active" : "") +
        '" data-mode="' + m + '" aria-pressed="' + (m === vm ? "true" : "false") +
        '" title="' + label + '">' + label + "</button>";
    });
    seg += "</div>";
    parts.push(seg);
  }
  if (opts.showSort) {
    var sel = '<label class="sortsel-wrap"><span class="sortsel-label">' + T("sort_label") + "</span>" +
      '<select id="sortsel" class="sortsel">';
    SORT_OPTS.forEach(function (o) {
      sel += '<option value="' + o[0] + '"' + (o[0] === opts.sortValue ? " selected" : "") + ">" + T(o[1]) + "</option>";
    });
    sel += "</select></label>";
    parts.push(sel);
  }
  return '<div class="toolbar">' + parts.join("") + "</div>";
}

/** 排序比较器（供视图与刷新复用） */
export var SORTERS = {
  date_desc: function (a, b) { return (b.w.date || "").localeCompare(a.w.date || ""); },
  date_asc:  function (a, b) { return (a.w.date || "").localeCompare(b.w.date || ""); },
  rating_desc: function (a, b) { return (b.w.rating || 0) - (a.w.rating || 0); },
  duration_desc: function (a, b) { return (b.w.duration || 0) - (a.w.duration || 0); },
  code_asc: function (a, b) { return (a.w.code || "").localeCompare(b.w.code || ""); }
};
