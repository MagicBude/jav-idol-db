# 标签映射数据说明

本目录下的标签（genre）多语言映射数据，用于把各数据源返回的标签
（日文 / 英文 / 站点内部 id）统一翻译、归一化为中文展示标签。

本仓库的实现为**自有、自行维护**，不依赖任何外部镜像。

## 权威文件（单一来源）

| 文件 | 说明 |
|---|---|
| `genre.csv` | **唯一权威映射表**，由 `scripts/merge_genre.py` 把多份跨源表合并、按日文标签去重生成，并已补全 zh_cn/zh_tw。它同时承担两重角色：① 站点构建与搜索检索的来源（`scripts/genre_norm.py` 只读取此文件）；② 你可读的资料库（用 Excel 打开即可浏览/筛选全部标签）。 |
| `genre.xlsx` | 同上的样式化可读版本（冻结表头 + 彩色表头 + 自动列宽 + 筛选器），供人工浏览，不参与构建。 |

### 列说明

`id, url, ja, zh_cn, zh_tw, en, note, source`

- `ja`：原始标签键（日文优先；部分来源无日文时退化为英文 / 中文 / 站点 id）。
- `zh_cn` / `zh_tw` / `en`：各语言翻译（简中 `zh_cn` 由 `data/zh.json` 人工精修层最高优先补全，站点中文视图显示此列）。
- `source`：溯源列，记录该行由哪些原始来源合并而来（如 `javbus;javlib`）。
- 注：`translate`（各源站原站中文翻译）仅作为 `zh_cn` 的内部补全兜底，不输出到面向读者的文档。

### 重新生成

```bash
python scripts/merge_genre.py
```

会从 `legacy/` 下读取原始分源 CSV，重新合并、去重，并刷新
`genre.csv` 与 `genre.xlsx`。

## 原始分源（已归档）

`legacy/` 下保留 5 份原始跨站映射表，仅供溯源与重新合并使用，
**不再被构建流程直接读取**：

| 原文件 | 原站点 | 说明 |
|---|---|---|
| `legacy/genre_javbus.csv` | javbus / busfan | 标签 id → 中/日/英 |
| `legacy/genre_javdb.csv` | javdb | 标签 id → 中/英 |
| `legacy/genre_javlib.csv` | javlibrary | 标签 id → 中/日/英 |
| `legacy/genre_avsox.csv` | avsox | 标签 id → 中/日/英 |
| `legacy/genre_jav321.csv` | jav321 | 标签 id → 中/日（日文在 translate 列） |

## 消费方式

映射逻辑见 `scripts/genre_norm.py`（独立实现）。权威表统一支持以下
可作为「键」的列：`ja`（日文）/ `en`（英文）/ `id`；作为「值」的列优先
`zh_cn`，否则 `zh_tw`。
