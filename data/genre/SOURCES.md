# 标签映射数据说明

本目录下的 `genre_*.csv` 为本仓库自有、自行维护的成人影片类型标签（genre）多语言事实映射数据，
用于把各数据源返回的标签（日文 / 英文 / 站点内部 id）统一翻译、归一化为中文展示标签。

## 文件清单

| 文件 | 原站点 | 说明 |
|---|---|---|
| `genre_javbus.csv` | javbus / busfan | 标签 id → 中/日/英 |
| `genre_javdb.csv` | javdb | 标签 id → 中/英 |
| `genre_javlib.csv` | javlibrary | 标签 id → 中/日/英 |
| `genre_avsox.csv` | avsox | 标签 id → 中/日/英 |
| `genre_jav321.csv` | jav321 | 标签 id → 中/日 |

## 消费方式

映射逻辑见 `scripts/genre_norm.py`（独立实现）。各 CSV 列不完全一致，统一支持以下可作为「键」的列：
`id` / `ja`（日文）/ `en`（英文）；作为「值」的列优先 `zh_cn`，否则 `zh_tw`，否则 `translate`。
