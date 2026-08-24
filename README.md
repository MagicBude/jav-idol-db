# jav-idol-db

日本 AV 女优与番号元数据资料库 · 纯静态站点（GitHub Pages）· 数据来自 codeav 等公开源站 ·
收录女优资料 / 番号 / 片名 / 封面图 · 服务于**个人网盘文件规范化整理**与社区查阅。

> 本仓库定位为「情报预处理中心」：先把女优资料、番号、片名、发行日、封面图集中搜集齐全，
> 之后再去改 115 网盘里的文件，就变成「查番号 → 拿标题+日期 → 套命名规则改名」的机械化操作，
> 比每次临时抓网省事太多。网站是母集，改名只是它的一个消费场景。

## 功能

- 女优检索：按名字 / 别名查女优档案（生日、身高、三围、所属、简介、头像）
- 番号检索：按番号（如 `IPX-005`）查作品（真实日文片名、发行日、女优、标签、封面）
- 静态站点：零服务器成本，部署到 GitHub Pages 后任何人都可访问
- 数据可追溯：每位女优、每部作品都是一个 JSON 文件，可发 PR 补充 / 修正

## 目录结构

```
jav-idol-db/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── schema.md          # 数据字段契约（女优 / 作品 JSON）
│   └── sources.md         # 数据来源、抓取方式、合规说明
├── data/                  # 核心数据（仓库真相源，仅 JSON）
│   ├── actresses/<女优名>/
│   │   ├── profile.json   # 女优档案
│   │   └── works/<番号>.json   # 每部作品
│   └── index.json         # 由 data 构建的汇总索引（程序 / API 用）
├── site/                  # 静态站点（GitHub Pages 部署此目录，自包含）
│   ├── index.html
│   ├── actress.html / work.html
│   ├── assets/
│   │   ├── css/style.css
│   │   ├── js/{data.js, app.js}   # data.js 由 build_index 生成
│   │   └── img/<女优名>/           # 头像 + 作品封面（入库）
├── scripts/               # 抓取 + 构建（Python 3，标准库为主）
│   ├── scrape_codeav.py   # 按番号从 codeav 抓作品元数据
│   ├── fetch_images.py    # 抓头像 / 封面到 data/images
│   └── build_index.py     # 由 data/ 生成 data/index.json 与站点用的 data.js
└── .github/workflows/deploy.yml
```

## 本地预览

站点读取 `data/index.json`，以及 `site/assets/js/data.js`（内联副本，便于 `file://` 双击打开）。
推荐用本地服务器预览（避免浏览器对 `file://` 的限制）：

```bash
cd jav-idol-db
python -m http.server 8000
# 浏览器打开 http://localhost:8000/site/
```

## 构建索引

```bash
python scripts/build_index.py
```

`build_index.py` 会扫描 `data/` 下所有 `profile.json` 与 `works/*.json`，生成：
- `data/index.json`（给程序 / API 用）
- `site/assets/js/data.js`（`window.JAV_DB = {...}`，给站点用，支持 `file://` 打开）

## 抓取数据

```bash
python scripts/scrape_codeav.py IPX-005            # 抓单个番号
python scripts/scrape_codeav.py IPX-005 IPX-006     # 抓多个
python scripts/scrape_codeav.py --actress 桃乃木かな --codes-file codes.txt
```

抓取到的作品会写入 `data/actresses/<女优>/works/<番号>.json`，再跑 `build_index.py` 即可上线。

## 部署到 GitHub Pages

1. 在 GitHub 建空仓库 `jav-idol-db`（**不要**勾选初始化 README / LICENSE / .gitignore）
2. 本地初始化并提交：
   ```bash
   git init
   git add .
   git commit -m "chore: 初始化 jav-idol-db 项目结构与种子数据"
   git branch -M main
   git remote add origin git@github.com:<你的用户名>/jav-idol-db.git
   git push -u origin main
   ```
3. 仓库 Settings → Pages → Source 选 `main` 分支、`/site` 目录 → Save
4. 之后每次 push 到 `main`，`.github/workflows/deploy.yml` 会自动跑 `build_index.py` 并部署

## 合规说明

- 图片仅收录**宣传 / 封面类肖像**，不含露骨内容，遵守 GitHub ToS。
- 元数据（女优名、番号、发行日、片名）为公开索引信息，来源为 codeav 等公开站点。
- 仓库默认建议 **Private**，确认内容无误后再改为 Public。
