# 标签映射数据来源说明

本目录下的 `genre_*.csv` 为 **成人影片类型标签（genre）的多语言事实映射数据**，用于把各数据源返回的标签（日文 / 英文 / 站点内部 id）统一翻译、归一化为中文展示标签。

## 来源

- 原项目：**JavSP**（社区维护的 JAV 元数据刮削器）
- 原始路径：`JavSP/data/genre_*.csv`
- 原项目许可证：**GNU GPL-3.0**

| 文件 | 原站点 | 说明 |
|---|---|---|
| `genre_javbus.csv` | javbus / busfan | 标签 id → 中/日/英 |
| `genre_javdb.csv` | javdb | 标签 id → 中/英 |
| `genre_javlib.csv` | javlibrary | 标签 id → 中/日/英 |
| `genre_avsox.csv` | avsox | 标签 id → 中/日/英 |
| `genre_jav321.csv` | jav321 | 标签 id → 中/日 |

## 许可证与复用边界

- 这些 CSV 是**事实性标签映射数据**（genre id ↔ 多语言名称），作为独立第三方数据资产存放在本仓库，文件本身沿用上游 GPL-3.0 的出处声明要求。
- 本仓库（`jav-idol-db`）整体以 **MIT** 许可证发布，覆盖我们自行编写的代码（`scripts/genre_norm.py` 等）；本目录的数据文件为独立资产，其上游许可证归属 JavSP 原作者。
- **消费方式**：`scripts/genre_norm.py` 自行实现映射逻辑并加载这些 CSV，不复制 JavSP 的源码。

## 字段约定

各 CSV 列不完全一致，统一支持以下可作为「键」的列：`id` / `ja`（日文）/ `en`（英文）；作为「值」的列优先 `zh_cn`，否则 `zh_tw`，否则 `translate`。
