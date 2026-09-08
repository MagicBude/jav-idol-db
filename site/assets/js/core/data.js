// core/data.js — 数据访问层（取数单一入口）
//
// 职责：读取 window.JAV_DB（由 scripts/build_index.py 生成），把它从「按女优嵌套」的
// 原始结构，扁平化为「按作品」的查询友好结构，并暴露分组/筛选/搜索助手。
// 依赖：仅依赖 window.JAV_DB（全局），不碰 DOM、不依赖其他 core 模块 —— 可独立单测。
// 约定：所有视图/组件都从这里取数，禁止各自直接读 window.JAV_DB，避免重复遍历与漂移。

var DB = window.JAV_DB || { actresses: [], counts: {}, zh: {} };
var ZH = DB.zh || {};

export var ACTRESS_ZH = ZH.actress_zh || {};   // 日文女优名 -> 中文名
export var TAG_ZH = ZH.tag_zh || {};           // 日文标签 -> 中文

// 反向映射：中文 -> 日文（用于中文搜索命中）
export var ZH_TO_JP_ACTRESS = {};
Object.keys(ACTRESS_ZH).forEach(function (jp) { ZH_TO_JP_ACTRESS[ACTRESS_ZH[jp]] = jp; });
export var ZH_TO_JP_TAG = {};
Object.keys(TAG_ZH).forEach(function (jp) { ZH_TO_JP_TAG[TAG_ZH[jp]] = jp; });

// 女优列表（集中导出，视图层统一从这里取，避免散落读 window.JAV_DB）
export var ACTRESSES = DB.actresses || [];

// 扁平化作品（带上归属女优与头像）：[{ w, owner, ownerAvatar }]
export var WORKS = [];
export var BY_CODE = {};
DB.actresses.forEach(function (a) {
  (a.works || []).forEach(function (w) {
    var rec = { w: w, owner: a.name, ownerAvatar: a.avatar };
    WORKS.push(rec);
    BY_CODE[w.code] = rec;
  });
});

// 全量 JP->ZH 标签映射：由每条作品的 tags / tags_zh 并行构建（genre_norm 已产出中文）
// 覆盖率 ~99.98%；不足时回退到 zh.json 手工 tag_zh 与原文。
export var GLOBAL_TAG_ZH = {};
DB.actresses.forEach(function (a) {
  (a.works || []).forEach(function (w) {
    var ts = w.tags || [], tz = w.tags_zh || [];
    if (ts.length && tz.length && ts.length === tz.length) {
      for (var i = 0; i < ts.length; i++) {
        if (ts[i] && tz[i] && !(ts[i] in GLOBAL_TAG_ZH)) GLOBAL_TAG_ZH[ts[i]] = tz[i];
      }
    }
  });
});

export function actressByName(name) {
  var found = null;
  DB.actresses.forEach(function (x) { if (x.name === name) found = x; });
  return found;
}

export function actressCount() {
  return DB.counts && DB.counts.actresses ? DB.counts.actresses : DB.actresses.length;
}
export function workCount() { return WORKS.length; }

/** 按类型/值筛选（t 标签 / m 片商或厂牌 / s 系列 / d 导演） */
export function filterByType(type, value) {
  return WORKS.filter(function (r) {
    var w = r.w;
    if (type === "t") return (w.labels || []).concat(w.tags || [], w.tags_zh || []).indexOf(value) >= 0;
    if (type === "m") return w.maker === value || w.label === value;
    if (type === "s") return w.series === value;
    if (type === "d") return (w.director || "") === value;
    return false;
  });
}

/** 中文感知搜索：番号 / 片名 / 女优(中或日) / 厂牌 / 系列 / 标签(中或日) */
export function searchWorks(q, matchFn) {
  if (!q) return WORKS.slice();
  return WORKS.filter(function (r) { return matchFn(r, q.toLowerCase()); });
}

/**
 * 给定路由 main/param，返回当前视图的作品列表（供首次渲染与排序刷新复用）。
 * 注意：这里只负责「取数」，排序由调用方用 SORTERS 完成。
 */
export function getViewRecs(main, param) {
  if (main === "a") {
    var a = actressByName(param);
    return (a ? a.works : []).map(function (w) { return BY_CODE[w.code] || { w: w, owner: a.name }; });
  }
  if (main === "t") return filterByType("t", param);
  if (main === "m") return filterByType("m", param);
  if (main === "s") return filterByType("s", param);
  if (main === "d") return filterByType("d", param);
  if (main === "q") return null; // 搜索由 router 用 searchWorks 处理
  return WORKS.slice();
}

// ---- 分组（人物/作品按维度聚合）----

var UNKNOWN = "__unknown__";

/**
 * 女优按事务所(agency)分组，对应「人物按事务所分」。
 * 返回 [{ agency, count, actresses }]，按组内人数降序；无事务所者归入 null 组并置底。
 * 视图层据此渲染分组标题 + 组内女优网格。
 */
export function groupActressesByAgency() {
  var map = {};
  ACTRESSES.forEach(function (a) {
    var key = a.agency || UNKNOWN;
    (map[key] = map[key] || []).push(a);
  });
  return Object.keys(map)
    .map(function (k) { return { agency: k === UNKNOWN ? null : k, count: map[k].length, actresses: map[k] }; })
    .sort(function (x, y) {
      if (!x.agency) return 1;   // 未知组永远置底
      if (!y.agency) return -1;
      return y.count - x.count;   // 人数多的组在前
    });
}

/**
 * 作品按某字段分组（maker/label/series/director/year 等），对应「作品按厂商分」等。
 * 返回 [{ key, count, recs }]，按数量降序；空值归入 null 组置底。
 * recs 缺省取全部 WORKS；传入子集可做二次聚合（如某女优的作品再按年份分）。
 */
export function groupWorksBy(field, recs) {
  recs = recs || WORKS;
  var map = {};
  recs.forEach(function (r) {
    var v = (field === "year") ? (r.w.date || "").slice(0, 4) : (r.w[field] || "");
    var key = v || UNKNOWN;
    (map[key] = map[key] || []).push(r);
  });
  return Object.keys(map)
    .map(function (k) { return { key: k === UNKNOWN ? null : k, count: map[k].length, recs: map[k] }; })
    .sort(function (x, y) {
      if (!x.key) return 1;
      if (!y.key) return -1;
      return y.count - x.count;
    });
}
