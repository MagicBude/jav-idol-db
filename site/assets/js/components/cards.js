// components/cards.js — 卡片与网格组件（作品卡 / 女优卡 / 标签 chip）
//
// 设计取向（学 JavBoss，去「AI 模板感」）：
//  · 封面占比大、圆角收敛、阴影克制；
//  · 卡内信息密度高：番号(mono) / 片名 / 日期·时长·女优 一行；
//  · 悬停浮出「外部来源圆形角标层」（可开关，见 core/state.getHoverSrc）。

import { esc, imgTag, enc } from "../core/util.js";
import { T, actressName, tagName, workTitle } from "../core/i18n.js";
import { getViewMode, getLang, getHoverSrc } from "../core/state.js";
import { sourceIconChips } from "../core/sources.js";

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
    ? '<img class="img img--poster" src="' + esc(poster) + '" alt="' + esc(w.code) + '" referrerpolicy="no-referrer" onerror="this.style.display=\'none\'">' +
      '<img class="img img--cover" src="' + esc(fanart) + '" alt="' + esc(w.code) + '" referrerpolicy="no-referrer" onerror="this.style.display=\'none\'">'
    : '<span class="ph">' + esc(w.code) + "</span>";

  var hover = getHoverSrc()
    ? '<div class="srclayer">' + sourceIconChips(w) + "</div>"
    : "";

  var dur = w.duration ? (w.duration + (getLang() === "zh" ? "分" : "分")) : "";
  var metaParts = [];
  if (w.date) metaParts.push(esc(w.date));
  if (dur) metaParts.push(esc(dur));
  if (rec.owner) metaParts.push(esc(actressName(rec.owner)));
  var meta = metaParts.length ? '<div class="meta">' + metaParts.join('<span class="dot">·</span>') + "</div>" : "";

  return (
    '<a class="card" href="#/w/' + enc(w.code) + '">' +
      '<div class="thumb">' + thumb + rating + incomplete + hover + "</div>" +
      '<div class="body">' +
        '<div class="code">' + esc(w.code) + "</div>" +
        '<div class="title">' + title + "</div>" +
        meta +
      "</div>" +
    "</a>"
  );
}

/** 作品网格（仅作品网格带 grid--work，受视图模式影响） */
export function workGrid(recs) {
  if (!recs.length) return '<div class="empty">' + T("empty_works") + "</div>";
  return '<div class="grid grid--work grid--' + getViewMode() + '">' + recs.map(workCard).join("") + "</div>";
}

/** 作品详情页的「预览图」缩略图组（sample_images，可选） */
export function sampleThumbs(w) {
  var imgs = w.sample_images || [];
  if (!imgs.length) return "";
  return '<div class="samples">' + imgs.slice(0, 12).map(function (u) {
    return '<a class="sample" href="' + esc(u) + '" target="_blank" rel="noopener">' +
      imgTag(u, w.code) + "</a>";
  }).join("") + "</div>";
}

/** 女优卡片：始终竖版，不受作品视图模式影响 */
export function actressCard(a) {
  return (
    '<a class="card actress" href="#/a/' + enc(a.name) + '">' +
      '<div class="thumb">' +
        imgTag(a.avatar, a.name, "img") +
        (a.avatar ? "" : '<span class="ph">' + esc(a.name) + "</span>") +
      "</div>" +
      '<div class="body"><div class="code">' + esc(actressName(a.name)) + "</div>" +
      '<div class="meta">' + (a.work_count || 0) + " " + T("f_works") + "</div></div></a>"
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
