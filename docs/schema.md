# 数据字段契约（schema）

本仓库所有数据都是 JSON 文件，分两类：**女优档案** 与 **作品**。
字段尽量保持向后兼容：新增字段时旧数据缺字段，前端用「待抓取 / 未知」兜底，不报错。

---

## 1. 女优档案 `data/actresses/<女优名>/profile.json`

文件名用女优**日文原名**（如 `桃乃木かな`），含中文/英文别名时放进 `aliases`。

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `name` | string | 女优名（日文原名，主键） | `桃乃木かな` |
| `aliases` | string[] | 别名 / 罗马音 / 中文译名 | `["Momonogi Kana"]` |
| `birthdate` | string? | 生日 `YYYY-MM-DD`，未知为 `null` | `1996-12-24` |
| `height` | int? | 身高（cm），未知为 `null` | `160` |
| `measurements` | string? | 三围，如 `B95(C)/W58/H85`，未知为 `null` | `B95/W58/H85` |
| `agency` | string? | 所属事务所，未知为 `null` | `T-POWERS` |
| `avatar` | string? | 头像相对路径（入库到 `site/assets/img/<名>/avatar.jpg`） | `assets/img/桃乃木かな/avatar.jpg` |
| `bio` | string | 简介（可空） | `""` |
| `source` | string | 数据来源标识 | `codeav` / `seed` / `manual` |
| `updated_at` | string | 最后更新日期 `YYYY-MM-DD` | `2026-08-24` |

> 注：`work_count` 与 `codes` 列表**不**存在 profile 里——由 `build_index.py` 扫描该女优
> `works/` 目录实时聚合，避免重复维护、出现不一致。

---

## 2. 作品 `data/actresses/<女优名>/works/<番号>.json`

文件名用**标准番号大写**（如 `IPX-005.json`、`SAMPLE-264.json`）。

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `code` | string | 标准番号（主键） | `IPX-005` |
| `title` | string | 真实日文片名；未抓到为 `""` | `問題児クラスを…フェラテクニック` |
| `date` | string? | 发行日 `YYYY-MM-DD`（FANZA 实体/DVD 发行日），未知为 `null` | `2014-09-19` |
| `actress` | string | 女优名（与 profile.name 对应） | `桃乃木かな` |
| `series` | string? | 系列名（真实系列，非番号前缀） | `噂の本番できちゃうおっパブ店` |
| `maker` | string? | 厂商 / Studio | `アイデアポケット` |
| `label` | string? | 厂牌 / Label | `ティッシュ` |
| `duration` | int? | 时长（分钟），未知为 `null` | `119` |
| `labels` | string[] | 标签（兼容字段，可后续从 label 派生） | `[]` |
| `tags` | string[] | 类型标签（从 codeav /genre/ 链接提取，去重去噪） | `["巨乳", "美少女", "単体作品"]` |
| `synopsis` | string? | 剧情简介 / Blurb | `【都内某所にある…】リピーター続出！…` |
| `rating` | float? | 评分（如 4.5），未知为 `null` | `4.5` |
| `rating_count` | int? | 评价数，未知为 `null` | `56` |
| `cover` | string? | 封面图 URL 或相对路径 | `https://awsimgsrc.dmm.co.jp/...ipx00005pl.jpg` |
| `segments` | int? | 分卷数（多 part 时），单文件为 `null` | `3` |
| `source` | string | 数据来源标识 | `codeav` / `115-rename-plan` / `seed` |
| `source_url` | string? | 来源页 URL，便于复核 / 补抓 | `https://www.codeav.net/movie/ipx-005` |
| `updated_at` | string | 最后更新日期 | `2026-08-24` |

---

## 3. 汇总索引 `data/index.json`（构建产物，勿手改）

由 `scripts/build_index.py` 生成，结构：

```json
{
  "generated_at": "2026-08-24T11:30:00",
  "counts": { "actresses": 1, "works": 3 },
  "actresses": [
    {
      "name": "桃乃木かな",
      "aliases": ["Momonogi Kana"],
      "avatar": "data/images/桃乃木かな/avatar.jpg",
      "work_count": 3,
      "codes": ["IPX-005", "SAMPLE-264"],
      "works": [ { "<作品字段...>" }, ... ]
    }
  ]
}
```

站点 `site/assets/js/data.js` 是同一份数据的 `window.JAV_DB = <json>` 内联副本，
便于 `file://` 双击打开（无需 HTTP 服务器）。
