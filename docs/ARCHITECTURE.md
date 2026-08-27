# 项目架构说明（ARCHITECTURE）

> 本文档描述 **当前真实架构**（截至 2026-08-27）。
> 配套文档：`README.md`（项目概览）、`docs/schema.md`（数据字段契约）、`docs/sources.md`（数据来源）。
> 注意：部分旧文档仍按「本地存图 / 多 HTML 页」的旧设计描述，与本文冲突处**以本文为准**。

---

## 1. 定位与一句话架构

`jav-idol-db` 是一个 **JAV 元数据归档 + 个人收藏规范化** 项目。
核心思想：**先把女优 / 番号 / 片名 / 封面等公开索引级元数据集中成结构化 JSON，再做下游消费**（115 网盘批量改名、静态站点查阅）。

```
                 ┌───────────────── 摄入层 (Ingest) ─────────────────┐
   公开源站        │  scripts/sources/*  (codeav/javbus/javdb/fanza)   │
 codeav/DMM  ───► │  tools/jav.py (CLI) · meta_store.py (持久层)       │
 javbus/javdb     │  scrape_*.py / update_metadata.py (批量回补)       │
                 └───────────────┬───────────────────────────────────┘
                                 │ 写入
                                 ▼
        ┌──────────────── 数据层 (Data · 仓库真相源) ────────────────┐
        │  data/works/<番号>.json           ← 扁平库(规范源, 1656)    │
        │  data/actresses/<名>/works/*.json ← 嵌套库(旧布局, 2293)    │
        │  data/actresses/<名>/profile.json ← 女优档案(16)            │
        │  data/zh.json · data/index.json(构建产物)                    │
        └────────────────────────┬───────────────────────────────────┘
                                 │ 富化 (Enrich)
                                 ▼
        ┌──────────────── 富化层 (Enrich) ────────────────┐
        │  cover_backfill.py · fill_avatars.py            │  (DMM 图床热链, HTTP 校验)
        └────────────────────────┬────────────────────────┘
                                 │ 构建 (Build · 纯函数)
                                 ▼
        ┌──────────────── 构建层 (Build) ─────────────────┐
        │  scripts/build_index.py                          │
        │   → data/index.json + site/assets/js/data.js    │
        └───────────┬───────────────────────┬────────────┘
                    │                         │
           展示层(SPA)                   本地服务
        ┌───────────▼──────────┐   ┌─────────▼──────────┐
        │ site/ (GitHub Pages) │   │ tools/serve.py     │
        │ index.html+app.js    │   │ + tools/webui/     │
        └───────────┬──────────┘   └─────────┬──────────┘
                    │                         │
                    ▼ 消费层 (Consume)         ▼
            tools/115rename.py (115 网盘批量改名)

   CI/CD: .github/workflows/deploy.yml — push main 时跑 build_index 并发布 site/ 到 Pages
```

---

## 2. 分层职责

### 2.1 数据层（`data/` · 仓库唯一真相源）
所有元数据都是 **JSON 文件**，按实体拆分，便于发 PR、可追溯、无数据库依赖。

| 路径 | 作用 | 状态 |
|---|---|---|
| `data/works/<番号>.json` | **扁平库**，每部作品一个文件，**规范源 / 优先** | 活，1656 个 |
| `data/actresses/<名>/works/<番号>.json` | **嵌套库**，旧布局，覆盖面更广（含 VR/写真），但含残缺旧抓 | 活但仅作「补缺」 |
| `data/actresses/<名>/profile.json` | 女优档案（avatar/bio/三围等） | 16 个有，其余靠占位 |
| `data/zh.json` | 中文层：`actress_zh` / `tag_zh` 映射 | 活 |
| `data/index.json` | **构建产物**，汇总索引（程序/API 用） | 每构建覆盖，**勿手改** |

**双布局并集规则**（`build_index.py`）：扁平库优先；嵌套库仅在「扁平库没有该番号 **且** title+date 齐全」时补缺，避免把残缺旧抓灌入网站。两库冲突时扁平库胜出。

> ⚠️ 双布局是历史包袱：嵌套库里存在空码 / 缺 title 的旧抓，曾引发「静默丢作品」bug（空码互相覆盖）。详见第 6 节。

### 2.2 摄入层（Ingest）
负责从外部源站抓取元数据写回数据层。

- **`scripts/sources/`**：抓取内核抽象。`base.py`(UA/canon/normalize) + `codeav.py`(urllib 直连,沙箱可达) + `javbus/javdb/fanza/javlibrary/websearch.py`(需本机宽网+Playwright,沙箱优雅降级)。**这是唯一应长期维护的抓取库。**
- **`tools/jav.py`**：用户态 CLI（`code`/`actress`/`search`/`normalize`），复用 `sources/`，输出标准化 JSON。`--source all` 多源并发合并。
- **`tools/meta_store.py`**：通用持久层（一次抓取、永久存档）。
- **`scripts/scrape_codeav.py` / `scrape_all.py` / `update_metadata.py`**：早期批量抓取 / 多源回补脚本，与 `sources/`+`jav.py` **职责高度重叠**，属待合并的重复实现（见第 6 节）。

### 2.3 富化层（Enrich）
补全封面 / 头像等图床链接（**全部热链 DMM，不下载到仓库**）。

- **`tools/cover_backfill.py`**：封面回填（已用，覆盖率 ~99.9%）。从已有 DMM 封面反推厂牌模板 + HTTP 校验回填。
- **`tools/fill_avatars.py` + `verify_avatars.py`**：女优头像回填（已用，17/17 真人女优覆盖）。

> 早期冗余脚本 `scripts/repair_covers.py` / `fetch_avatars.py` / `fetch_images.py` 已在 P1b 清理删除（功能已并入上述两个工具，且 `fetch_images` 与本项目的「全热链」策略矛盾）。

### 2.4 构建层（Build）
- **`scripts/build_index.py`**：**全站唯一构建入口**。扫描 `data/works/`（**单布局唯一真相源**）→ 按女优嵌套分组 → 实时聚合 `work_count`/`codes` → 写出 `data/index.json` 与 `site/assets/js/data.js`（`window.JAV_DB`）。支持 `--check` 仅校验。缺 `code` 字段的文件会被跳过并告警（不再静默丢数据）。
- 设计要点：构建是 **`data/` 的纯函数**，可重复、可在 CI 重跑，产物不进版本手动维护。

### 2.5 展示层（Presentation）
- **`site/`**：原生 JS 单页应用（SPA）。`index.html` + `assets/js/{app.js,data.js}` + `assets/css/style.css`。`data.js` 内联全量数据，支持 `file://` 双击打开。`app.js` 用 `<img referrerpolicy="no-referrer" onerror>` 渲染封面/头像（避免 CSS background 在浏览器层失败）。
- **`tools/serve.py` + `tools/webui/`**：本地交互式查询服务（零外部依赖，标准库 `http.server`）。

### 2.6 消费层（Consume）
- **`tools/115rename.py`**：115 网盘批量改名编排（按 `115-av-rename` 技能流程），消费 `data/works` 的 title/date/code。
- **`tools/rename_map.py`**：`jav.py` 输出的改名示例应用。
- **`tools/strip_actress.py`**：115 文件名「摘掉女优名后缀」安全脚本。

### 2.7 CI/CD
- **`.github/workflows/deploy.yml`**：`push` 到 `main` 时 → `python scripts/build_index.py` 重建 `data.js` → 上传 `site/` 到 GitHub Pages。即「提交数据即自动上线」。

---

## 3. 一次数据的生命周期

```
1) 抓：jav.py code IPX-005  → sources/codeav.py 直连 codeav → 标准化元数据
2) 存：写入 data/works/IPX-005.json（规范源，扁平库）
3) 富：cover_backfill / fill_avatars  → 补 DMM 图床热链（HTTP 校验）
4) 建：build_index.py  → 扁平单布局 → data/index.json + site/assets/js/data.js
5) 上：git push main  → deploy.yml 重建并发布到 GitHub Pages
6) 用：用户在站点查阅 / 115rename.py 读取 title+date 批量改名
```

---

## 4. 关键设计决策（及理由）

| 决策 | 选择 | 理由 |
|---|---|---|
| 存储形态 | **JSON 文件即真相源**，不引数据库 | 可发 PR、git 可追溯、零运维；规模（~2000 部）完全够 |
| 图片 | **全部热链 DMM 图床**，不下载入库 | 仓库体积小、规避二进制 / GitHub ToS 风险；与「情报预处理中心」定位一致 |
| 构建 | 单一 `build_index.py`，`data/` 的纯函数 | 可重复、CI 可重跑、产物不手工维护 |
| 数据布局 | **单布局 `data/works/<番号>.json` 唯一真相源** | 根绝双布局并集的「空码互相覆盖 → 静默丢作品」bug（见 6.3 历史问题） |
| 多源抓取 | `sources/` 抽象 + `--source all` 合并 | 单源不稳时互补，codeav 优先其余补缺 |
| 部署 | GitHub Pages + 自动构建 | 零服务器成本，提交即上线 |

---

## 5. 模块清单（含状态标注）

| 文件 | 职责 | 状态 |
|---|---|---|
| `scripts/sources/*` | 抓取内核（codeav/javbus/javdb/fanza…） | ✅ 活 · 应长期维护 |
| `tools/jav.py` | 用户态查询 CLI | ✅ 活 |
| `tools/meta_store.py` | 元数据持久层 | ✅ 活 |
| `scripts/build_index.py` | 全站唯一构建入口 | ✅ 活 |
| `tools/cover_backfill.py` | 封面回填（热链, 已用） | ✅ 活 |
| `tools/fill_avatars.py` `verify_avatars.py` | 头像回填（已用） | ✅ 活 |
| `tools/115rename.py` | 115 改名编排 | ✅ 活 |
| `tools/serve.py` `tools/webui/` | 本地查询服务 | ✅ 活 |
| `tools/strip_actress.py` `rename_map.py` | 改名辅助 | ✅ 活 |
| `scripts/scrape_codeav.py` | 早期 codeav 抓取 | ⚠️ 与 `sources/codeav.py` 重叠 |
| `scripts/scrape_all.py` | 批量抓取 | ⚠️ 与 `jav.py`/摄入层重叠 |
| `scripts/update_metadata.py` | 多源回补编排 | ⚠️ 与 `jav.py --source all` 重叠 |
| `scripts/repair_covers.py` `fetch_avatars.py` `fetch_images.py` | 早期冗余脚本 | 🗑️ P1b 已删除（并入 `cover_backfill`/`fill_avatars`） |
| `scripts/audit_attribution.py` | 嵌套库归属审计（仅 `--fix-attribution` 子命令残留引用） | 🟡 历史维护工具，单布局后作用减弱 |
| `scripts/fix_attribution.py` `reconcile_attribution.py` `_check_fanhao.py` | 旧嵌套库修复簇 / 零散脚本 | 🗑️ P1b 已删除 |

---

## 6. 当前问题 / 不规范之处（状态追踪）

> 标注：**✅ 已解决**（本轮优化）/ **🟡 部分解决** / **⬜ 未解决**（低优先级 P3）。

1. **文档与代码严重脱节（最突出）** — ✅ 已解决
   `README.md` / `docs/sources.md` 已刷新为「全热链 + 单页 SPA + CLI + 单布局构建」，并指向本文作为架构权威。

2. **脚本面条化 / 重复入口** — 🟡 部分解决
   富化层冗余脚本（`repair_covers`/`fetch_avatars`/`fetch_images`）已在 P1b 删除；`audit_attribution` 簇（`fix_attribution`/`reconcile_attribution`/`_check_fanhao`）已删。但摄入层 `scrape_codeav.py`/`scrape_all.py`/`update_metadata.py` 仍与 `tools/jav.py`(+`sources/`) 重叠，待 P1 收口为单一摄入命令。

3. **双数据布局的脆弱性** — ✅ 已解决
   已迁移到**单布局 `data/works/<番号>.json` 唯一真相源**（嵌套库删除）；`build_index.py` 改为只扫扁平库，缺 `code` 文件会跳过并告警，根绝「空码互相覆盖 → 静默丢作品」bug。

4. **无依赖清单 / 无测试 / 无构建入口统一** — ✅ 已解决
   已加 `pyproject.toml`（含 `project.scripts` 与 pytest 配置）、`Makefile`（`make build/serve/ingest/backfill/test`）、`tests/test_data_integrity.py`（5 项冒烟/回归护栏，已全部通过）。

5. **`tools/` 扁平堆放** — ⬜ 未解决（P3）
   通用工具与一次性女优脚本仍平铺在 `tools/`，可后续划分子包（`ingest/`/`rename/`/`web/`）。

---

## 7. 改进路线（建议优先级）

| 优先级 | 动作 | 收益 | 成本 | 状态 |
|---|---|---|---|---|
| P0 | 刷新 `README.md` / `docs/sources.md` 使其与本文一致；将本文设为架构权威 | 消除最大「不规范」源 | 低 | ✅ 已完成 |
| P1 | 确立**单一摄入命令**：以 `tools/jav.py`(+`sources/`) 为入口，废弃/合并 `scrape_*` / `update_metadata` | 消除重复入口 | 中 | 🟡 部分（冗余脚本已删，摄入层待收口） |
| P1 | 富化脚本合并：保留 `cover_backfill`/`fill_avatars`，删 `fetch_images`（废弃）、合并 `repair_covers`/`fetch_avatars` 逻辑 | 减少 ~2 套冗余 | 低 | ✅ 已完成 |
| P2 | **迁移到单一数据布局**：以 `data/works/` 为唯一源，移除嵌套库 | 根除双布局 bug | 中 | ✅ 已完成（2012 部，零丢失） |
| P2 | 加 `pyproject.toml` + `tests/` + `Makefile`(`make build/ingest/serve/test`) | 工程化、可测、可装 | 中 | ✅ 已完成（5/5 测试通过） |
| P3 | `tools/` 划分子包（`ingest/`、`rename/`、`web/`）或至少分组 | 可读性 | 低 | ⬜ 未做 |
| P3 | 移除 `scripts/_check_fanhao.py` 等疑似废弃脚本 | 清理 | 低 | ✅ 已完成 |
