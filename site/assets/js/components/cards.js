// components/cards.js — 卡片与网格组件（作品卡 / 女优卡 / 标签 chip）

import { esc, imgTag, enc } from "../core/util.js";
import { T, actressName, tagName, workTitle } from "../core/i18n.js";
import { getViewMode } from "../core/state.js";

/**
 * 作品卡片（单一标记，三种视图仅由 .grid--poster/.grid--cover/.grid--list 的 CSS 切换）。
 * - poster 模式：显示竖版图（poster || cover）
 * - cover  模式：显示横版图（background || cover）；JAV 来源通常只有竖版封面，故缺省回退同一封面
 * - list   模式：CSS 隐藏缩略图，改为行式纯文字
 */
export function workCard(rec) {
  var w = rec.w;
  var poster = w.poster || w.cover;
  var fanart = w.background || w.cover;
  var rating = w.rating ? '<span class="badge">★ ' + w.rating + "</span>" : "";
  var incomplete = w.incomplete ? '<span class="badge warn">' + T("badge_incomplete") + "</span>" : "";
  var title = workTitle(w) ? esc(workTitle(w)) : T("pending_title");
  var thumb = w.cover
    ? '<img class="img img--poster" src="' + esc(poster) + '" alt="' + esc(w.code) + '" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display=\'none\'">' +
      '<img class="img img--cover" src="' + esc(fanart) + '" alt="' + esc(w.code) + '" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display=\'none\'">'
    : '<span class="ph">' + esc(w.code) + "</span>";
  return (
    '<a class="card" href="#/w/' + enc(w.code) + '">' +
      '<div class="thumb">' + thumb + rating + incomplete + "</div>" +
      '<div class="body">' +
        '<div class="name">' + esc(w.code) + "</div>" +
        '<div class="sub">' + title + "</div>" +
        '<div class="meta">' + (w.date || "") + (rec.owner ? " · " + esc(actressName(rec.owner)) : "") + "</div>" +
      "</div>" +
    "</a>"
  );
}

/** 作品网格（仅作品网格带 grid--work，受视图模式影响） */
export function workGrid(recs) {
  if (!recs.length) return '<div class="empty">' + T("empty_works") + "</div>";
  return '<div class="grid grid--work grid--' + getViewMode() + '">' + recs.map(workCard).join("") + "</div>";
}

/** 女优卡片：始终竖版，不受作品视图模式影响 */
export function actressCard(a) {
  return (
    '<a class="card actress" href="#/a/' + enc(a.name) + '">' +
      '<div class="thumb">' +
        imgTag(a.avatar, a.name, "img") +
        (a.avatar ? "" : '<span class="ph">' + esc(a.name) + "</span>") +
      "</div>" +
      '<div class="body"><div class="name">' + esc(actressName(a.name)) + "</div>" +
      '<div class="sub">' + (a.work_count || 0) + " " + T("f_works") + "</div></div></a>"
  );
}

/** 女优网格（固定竖版，独立于作品视图模式） */
export function actressGrid(arr) {
  if (!arr.length) return '<div class="empty">' + T("empty_works") + "</div>";
  return '<div class="grid grid--actress">' + arr.map(actressCard).join("") + "</div>";
}

/** 可点击标签 / 片商 / 系列 chip */
export function chip(type, val) {
  if (!val) return "";
  var route = { t: "#/t/", m: "#/m/", s: "#/s/" }[type];
  var label = (type === "t") ? tagName(val) : val;
  return '<a class="chip" href="' + route + enc(val) + '">' + esc(label) + "</a>";
}
export function chips(type, arr) {
  if (!arr || !arr.length) return "";
  return arr.map(function (v) { return chip(type, v); }).join("");
}
