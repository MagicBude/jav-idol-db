# jav-idol-db

日本 AV 女优与番号元数据资料库 · 纯静态站点（GitHub Pages）· 数据来自 codeav 等公开源站 ·
收录女优资料 / 番号 / 片名 / 封面图 · 服务于**个人网盘文件规范化整理**与社区查阅。

> 本仓库定位为「情报预处理中心」：先把女优资料、番号、片名、发行日、封面图集中搜集齐全，
> 之后再去改 115 网盘里的文件，就变成「查番号 → 拿标题+日期 → 套命名规则改名」的机械化操作，
> 比每次临时抓网省事太多。网站是母集，改名只是它的一个消费场景。

## 文档

| 文档 | 内容 |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **架构权威说明**：分层、数据生命周期、设计决策、模块清单、改进路线 |
| [`docs/schema.md`](docs/schema.md) | 数据字段契约（女优 / 作品 JSON） |
| [`docs/sources.md`](docs/sources.md) | 数据来源、抓取方式、图片热链策略、合规说明 |

## 架构总览

```
数据源(codeav等) ──抓取──> data/works/<番号>.json  ┐
                                                 ├─ 唯一真相源(扁平 JSON)
data/actresses/<女优>/profile.json ────────────────┘
        │
        │ scripts/build_index.py（纯函数：data/ → 索引）
        ▼
data/index.json  +  site/assets/js/data.js(window.JAV_DB)
        │
        │ 推送到 main 分支
        ▼
.github/workflows/deploy.yml ──> GitHub Pages 自动部署 site/
```

- **数据即真相源**：每部作品一个 JSON 文件存于 `data/works/`（扁平单布局）。不引入数据库，
  可发 PR、git 可追溯。女优档案（`profile.json`）只含头像/简介等聚合信息，不含作品副本。
- **图片全热链**：封面走 DMM 图床、头像走 `awsimgsrc.dmm.co.jp`，**不下载、不入库**
  （仓库轻、规避二进制 / GitHub ToS）。详情见 [`docs/sources.md`](docs/sources.md) 第 4 节。
- **构建即纯函数**：`build_index.py` 是 `data/` 到索引的唯一入口，可重复、CI 可重跑。
- **推送即上线**：`deploy.yml` 在每次 push 时重建索引并发布 `site/` 到 GitHub Pages。

## 目录结构

```
jav-idol-db/
├── README.md
├── LICENSE
├── .gitignore
├── pyproject.toml          # 项目元数据 + 依赖 + 脚本入口
├── Makefile                # make build / ingest / serve 统一入口
├── docs/
│   ├── ARCHITECTURE.md     # 架构说明（权威）
│   ├── schema.md           # 数据字段契约
│   └── sources.md          # 数据来源与热链策略
├── data/                  # 核心数据（唯一真相源，仅 JSON）
│   ├── works/<番号>.json   # 每部作品（扁平布局，单一真相源）
│   ├── actresses/<女优>/profile.json   # 女优档案（头像/简介）
│   ├── index.json          # 由 build_index 生成的汇总索引（程序/API 用）
│   ├── zh.json             # 中文映射层（女优/标签中文名）
│   └── _code_meta_index.json  # 番号→文件路径缓存（O(1) 命中）
├── site/                  # 静态站点 SPA（GitHub Pages 部署此目录，自包含）
│   ├── index.html
│   └── assets/{css,js}/    # app.js(渲染) + data.js(由 build_index 生成)
├── scripts/               # 抓取 + 构建（Python 3，标准库为主）
│   ├── build_index.py      # 由 data/works 生成 data/index.json 与 site 用 data.js
│   ├── scrape_codeav.py    # 按番号从 codeav 抓作品元数据 → data/works
│   ├── scrape_all.py       # 批量重抓 data/works 全部作品（可续跑/并发）
│   ├── update_metadata.py  # 多源回补编排器（幂等，填空缺字段）
│   ├── audit_attribution.py# 归属审计（比对 codeav 主演）
│   └── sources/            # 多源抓取内核（codeav/fanza/javbus/javdb/javlibrary/websearch）
├── tools/                 # 查询 CLI + 115 工具链 + 富化脚本
│   ├── jav.py              # 查询 CLI（code/actress/search/normalize）
│   ├── meta_store.py       # 元数据持久层（抓取 + 落盘 data/works，O(1) 缓存）
│   ├── 115rename.py        # 115 网盘批量改名编排（按女优合集）
│   ├── cover_backfill.py   # 封面热链回填（DMM 模板 + HTTP 校验）
│   ├── fill_avatars.py     # 女优头像补全（DMM 写真图床 + HTTP 校验）
│   ├── serve.py            # 本地交互式查询界面（http.server，零依赖）
│   └── webui/              # serve.py 的前端
└── tests/                 # 冒烟测试（schema / build 校验）
```

## 本地预览

站点读取 `site/assets/js/data.js`（内联 `window.JAV_DB`，便于 `file://` 双击打开）。
推荐用本地服务器预览：

```bash
cd jav-idol-db
make serve            # 等价于 python -m http.server，默认 8766
# 浏览器打开 http://localhost:8766/
```

## 常用命令

```bash
make build           # 重新生成 data/index.json 与 site/assets/js/data.js（含字段完整性标注；--strict 可作 CI 卡口）
make audit           # 数据质量自检：字段覆盖率 / 女优作品数 / 缺关键字段清单
make ingest CODE=IPX-005        # 抓取单个番号元数据 → data/works
make ingest-all      # 批量重抓 data/works 全部作品
python tools/jav.py code IPX-005            # 查询某部作品（多源）
python tools/jav.py actress 桃乃木かな       # 查询某女优
python tools/115rename.py --cid <CID> --actress 八木奈々   # 115 改名(dry-run)
```

> 无 `make` 时，等价命令见 `Makefile` 与各脚本 `--help`；也可直接 `python scripts/build_index.py`。

## 抓取与回补

```bash
python scripts/scrape_codeav.py IPX-005                 # 抓单个番号
python scripts/scrape_all.py --pending                  # 批量回补缺标题的作品
python scripts/update_metadata.py --pending --hard      # 多源回补(含 javbus/javdb 攻克)
```

抓取到的作品写入 `data/works/<番号>.json`（单一真相源），再跑 `make build` 即可上线。
归属修正：`update_metadata.py --pending --fix-attribution` 会就地修正 work 的 `actress` 字段
（单布局下归属体现在字段里，不再在目录间搬文件）。

## 部署到 GitHub Pages

1. 仓库 Settings → Pages → Source 选 `main` 分支、`/site` 目录 → Save。
2. 之后每次 push 到 `main`，`.github/workflows/deploy.yml` 会自动跑 `build_index.py` 并部署
   （无需手动构建，CI 保证线上与 `data/` 一致）。

## 标签中文化与番号归一化

- **标签中文化**：构建期（`build_index.py`）调用 `scripts/genre_norm.py`，把每部作品 `tags`（多为日文/英文裸标签）翻译、归一化为中文 `tags_zh`，写入索引；站点优先展示中文标签。映射表来自多源 genre 数据（`data/genre/`，取自 JavSP，GPL-3.0，见 `SOURCES.md`），并以本仓库 `data/zh.json` 的 `tag_zh`（人工维护简中）优先覆盖。当前约 82.9% 的标签可映射为中文。
- **番号归一化**：`scripts/idnorm.py` 提供 `normalize_id()`（大小写/分隔符归一、>3 位去多余前导零、<=3 位保留）与 `guess_av_type()`（normal/fc2/getchu/gyutto/cid），用于番号匹配/去重，已带单测 `tests/test_idnorm.py`。（借鉴 JavSP `avid.py` 思路，独立实现以规避 GPL 传染。）

## 合规说明

- 图片仅热链**宣传 / 封面类肖像**（DMM 图床），**不下载、不入库**，遵守 GitHub ToS。
- 元数据（女优名、番号、发行日、片名）为公开索引信息，来源为 codeav 等公开站点。
- 仓库默认建议 **Private**，确认内容无误后再改为 Public。
- 若某女优 / 作品要求撤下，及时 PR 删除对应 JSON。
