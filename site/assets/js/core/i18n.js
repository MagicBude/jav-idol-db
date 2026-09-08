// core/i18n.js — 多语言文案 + 显示名（随语言切换）
// 默认日本語，可一键切中文；数据显示名由 actressName / tagName / workTitle 决定。

import { getLang } from "./state.js";
import { ACTRESS_ZH, TAG_ZH, GLOBAL_TAG_ZH } from "./data.js";

export var UI = {
  ja: {
    brand: "IDOL DB", brand_sub: "資料庫",
    search_ph: "番号 / タイトル / 女優 / タグ で検索…",
    nav_discover: "探索", nav_library: "ライブラリ",
    nav_home: "ホーム", nav_works: "作品", nav_actresses: "女優",
    nav_tags: "タグ", nav_makers: "メーカー", nav_series: "シリーズ", nav_directors: "監督",
    nav_stats: "統計",
    sort_label: "並び替え",
    s_date_desc: "新着順", s_date_asc: "古い順", s_rating_desc: "評価順",
    s_duration_desc: "長い順", s_code_asc: "番号順",
    home_lead: function (a, w) {
      return a + " 名の女優 · " + w + " 本の作品 · 番号 / タイトル / 女優 / タグ で検索、タグ / メーカー / シリーズ で絞り込み";
    },
    stats_link: "統計 / 概要 →",
    actresses: "女優", hot_tags: "人気タグ", latest: "新着", all_works: "すべての作品",
    new_actresses: "新着女優", spotlight: "注目",
    stats_title: "資料庫概要",
    stats_lead: function (a, w, y0, y1) { return a + " 名の女優 · " + w + " 本の作品 · " + y0 + "–" + y1 + " 年"; },
    s_actresses: "女優", s_works: "作品", s_rated: "評価済み", s_avg: "平均評価",
    s_year: "年度別リリース数", s_maker: "メーカー Top 15", s_tag: "タグ Top 24",
    s_actress_rank: "女優別作品数 Top 15", s_director: "監督 Top 10",
    crumb_actress: "女優", crumb_all: "すべての作品", crumb_search: "検索", crumb_stats: "統計",
    f_aliases: "別名", f_birth: "誕生日", f_birthplace: "出身地", f_blood: "血液型",
    f_height: "身長", f_measure: "スリーサイズ", f_debut: "デビュー", f_agency: "事務所",
    f_status: "ステータス", f_retire: "引退日", f_comeback: "復帰日", f_reading: "読み",
    f_roman: "ローマ字", f_hobby: "趣味・特技", f_career: "出演期間", f_debut_work: "デビュー作",
    f_blog: "ブログ", f_site: "公式サイト", f_minnano: "みんなのAV",
    f_name_zh: "中国語名", f_baike: "百度百科", f_baike_search: "百度百科で検索",
    f_aliases_zh: "中国語別名", f_notable: "代表作", f_status_src: "状態出典",
    f_works: "作品数", f_span: "活動年", f_avg: "平均評価",
    f_incomplete: "⚠️ この作品のデータが不完全です。不足：",
    f_cast_date: "発売日", f_cast: "出演", f_maker: "メーカー", f_label: "レーベル",
    f_series: "シリーズ", f_duration: "時間", f_director: "監督", f_rating: "評価", f_synopsis: "あらすじ",
    f_bio: "プロフィール",
    flt_t: "タグ", flt_m: "メーカー / レーベル", flt_s: "シリーズ", flt_d: "監督",
    pending_title: "（タイトル未取得）", badge_incomplete: "データ不足",
    empty_works: "一致する作品がありません。",
    err_work: "未找到作品：", err_actress: "未找到女优：", err_page: "未知页面：",
    v_poster: "ポスター壁", v_cover: "カバー", v_list: "リスト",
    results: "検索結果"
  },
  zh: {
    brand: "IDOL DB", brand_sub: "资料库",
    search_ph: "搜索 番号 / 片名 / 女优 / 标签…",
    nav_discover: "探索", nav_library: "资料库",
    nav_home: "首页", nav_works: "作品", nav_actresses: "女优",
    nav_tags: "标签", nav_makers: "片商", nav_series: "系列", nav_directors: "导演",
    nav_stats: "统计",
    sort_label: "排序",
    s_date_desc: "最新发行", s_date_asc: "最早发行", s_rating_desc: "评分最高",
    s_duration_desc: "时长最长", s_code_asc: "番号排序",
    home_lead: function (a, w) {
      return a + " 位女优 · " + w + " 部作品 · 支持番号 / 片名 / 女优 / 标签检索，标签 / 片商 / 系列 一键筛选";
    },
    stats_link: "资料库总览 / 统计 →",
    actresses: "女优", hot_tags: "热门标签", latest: "最新发行", all_works: "全部作品",
    new_actresses: "新晋女优", spotlight: "精选",
    stats_title: "资料库总览",
    stats_lead: function (a, w, y0, y1) { return a + " 位女优 · " + w + " 部作品 · 跨 " + y0 + "–" + y1 + " 年"; },
    s_actresses: "女优", s_works: "作品", s_rated: "已评分作品", s_avg: "平均评分",
    s_year: "逐年发行量", s_maker: "片商 Top 15", s_tag: "标签 Top 24",
    s_actress_rank: "女优作品量 Top 15", s_director: "导演 Top 10",
    crumb_actress: "女优", crumb_all: "全部作品", crumb_search: "搜索", crumb_stats: "统计",
    f_aliases: "别名", f_birth: "生日", f_birthplace: "出身地", f_blood: "血型",
    f_height: "身高", f_measure: "三围", f_debut: "出道", f_agency: "事务所",
    f_status: "状态", f_retire: "引退日期", f_comeback: "复出日期", f_reading: "读音",
    f_roman: "罗马名", f_hobby: "兴趣特长", f_career: "出演期间", f_debut_work: "出道作品",
    f_blog: "博客 / 社媒", f_site: "官方网站", f_minnano: "minnano 档案",
    f_name_zh: "中文名", f_baike: "百度百科", f_baike_search: "搜索百度百科",
    f_aliases_zh: "中文别名", f_notable: "代表作", f_status_src: "状态来源",
    f_works: "作品数", f_span: "活动年份", f_avg: "平均评分",
    f_incomplete: "⚠️ 本作资料不全，缺失：",
    f_cast_date: "发行日", f_cast: "出演", f_maker: "片商", f_label: "厂牌",
    f_series: "系列", f_duration: "时长", f_director: "导演", f_rating: "评分", f_synopsis: "剧情简介",
    f_bio: "个人简介",
    flt_t: "标签", flt_m: "片商 / 厂牌", flt_s: "系列", flt_d: "导演",
    pending_title: "（片名待抓取）", badge_incomplete: "资料不全",
    empty_works: "没有匹配的作品。",
    err_work: "未找到作品：", err_actress: "未找到女优：", err_page: "未知页面：",
    v_poster: "海报墙", v_cover: "封面", v_list: "列表",
    results: "搜索结果"
  }
};

/** 取 UI 文案：当前语言优先，缺省回退中文 */
export function T(key) {
  var lang = getLang();
  var d = UI[lang] || UI.zh;
  var v = d[key];
  if (v === undefined) v = (UI.zh || {})[key];
  return v === undefined ? key : v;
}

// ---- 显示名（随语言切换）----
export function actressName(jp) {
  if (getLang() === "zh") return ACTRESS_ZH[jp] || jp;
  return jp;
}
export function tagName(jp) {
  if (getLang() === "zh") return GLOBAL_TAG_ZH[jp] || TAG_ZH[jp] || jp;
  return jp;
}
export function workTitle(w) {
  if (getLang() === "zh" && w && w.title_zh) return w.title_zh;
  return (w && w.title) || "";
}

// ---- 女优状态 ----
var ACTRESS_STATUS = {
  active:  { ja: "現役", zh: "在役" },
  retired: { ja: "引退", zh: "引退" },
  hiatus:  { ja: "活動休止", zh: "休业" },
  unknown: { ja: "不明", zh: "不明" }
};
export function statusText(code) {
  var m = ACTRESS_STATUS[code || "unknown"] || ACTRESS_STATUS.unknown;
  return m[getLang()] || m.zh;
}
export function statusClass(code) { return "st-" + (code || "unknown"); }

/** 中文感知搜索：q 已 lowercased；命中 番号/片名/女优(中或日)/厂牌/系列/标签(中或日) */
export function workMatchesQuery(r, q) {
  if (!q) return true;
  var w = r.w;
  if ((w.code || "").toLowerCase().indexOf(q) >= 0) return true;
  var t = workTitle(w);
  if (t && t.toLowerCase().indexOf(q) >= 0) return true;
  var o = r.owner || "";
  if (o.toLowerCase().indexOf(q) >= 0) return true;
  if ((ACTRESS_ZH[o] || "").toLowerCase().indexOf(q) >= 0) return true;
  if ((w.actress_search || []).some(function (x) { return x.toLowerCase().indexOf(q) >= 0; })) return true;
  if ((w.maker || "").toLowerCase().indexOf(q) >= 0) return true;
  if ((w.label || "").toLowerCase().indexOf(q) >= 0) return true;
  if ((w.series || "").toLowerCase().indexOf(q) >= 0) return true;
  if ((w.tags || []).some(function (x) {
    return x.toLowerCase().indexOf(q) >= 0 || ((GLOBAL_TAG_ZH[x] || TAG_ZH[x] || "").toLowerCase().indexOf(q) >= 0);
  })) return true;
  if ((w.tags_zh || []).some(function (x) { return x.toLowerCase().indexOf(q) >= 0; })) return true;
  return false;
}
