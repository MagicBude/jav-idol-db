// core/util.js — 通用工具函数（无依赖）
// 只放纯函数，方便单元测试与组件复用。

/** HTML 转义：防止用户数据中的 < > & " 破坏结构或注入 */
export function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** 生成 <img>：用 img 标签而非 background，支持懒加载 / referrer / onerror 降级 */
export function imgTag(url, alt, cls) {
  if (!url) return "";
  return '<img class="' + (cls || "") + '" src="' + esc(url) + '" alt="' + esc(alt || "") + '" ' +
    'loading="lazy" referrerpolicy="no-referrer" ' +
    'onerror="this.style.display=\'none\'">';
}

/** 解码 hash 段（支持中文 / 特殊字符） */
export function dec(s) {
  try { return decodeURIComponent(s); } catch (e) { return s; }
}

/** 编码 hash 段 */
export function enc(s) {
  return encodeURIComponent(s);
}

/** 安全取整型（用于 duration / rating 排序容错） */
export function num(v, d) {
  var n = typeof v === "number" ? v : parseFloat(v);
  return isNaN(n) ? (d || 0) : n;
}
