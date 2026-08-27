# 数据来源与抓取说明（sources）

## 1. 主源：codeav.net（FANZA/DMM 元数据镜像，静态页）

- 影片页：`https://www.codeav.net/movie/{标准番号小写}`（如 `ipx-005`）
  - `<h1>` 即**真实日文片名**（最稳，约 97% 覆盖）
  - 页面内 JSON-LD 含 `"datePublished":"YYYY-MM-DD"`（FANZA 实体/DVD 发行日）
- 内码页：`https://www.codeav.net/cid/{内码}`（如 `1stars00145`）
  - `<dt>Released</dt><dd>October 22, 2019</dd>` 英文月份日期
  - `/en/cid/` 会 301 到 `/cid/`，抓取需跟随重定向
- 抓取方式：`urllib` 直接请求即可（见 `scripts/scrape_codeav.py`），无需无头浏览器。
- 已知少量码在 codeav 真 404（稀有 / 样品盘），这类走下方备选源或直接标「待补」。

## 2. 备选源（codeav 缺失时）

| 源 | 用法 | 备注 |
|---|---|---|
| WebSearch 搜索引擎 | `WebSearch "{番号} 女优名 発売日"` | 沙箱内最稳，走搜索索引不受出网限制 |
| hornyjav.net | 搜索 `?s={番号}` | 沙箱偶发 SSL 拦截 |
| themoviedb | 实体发行日 | 与 codeav 同口径（碟发售日），优于流媒日 |
| javlibrary / javbus | 交叉印证 | 沙箱常连不通 |

> 日期取源优先级：**themoviedb 实体发行日** > 多源一致 > 流媒日（流媒比实体盘早约 1 个月，慎用）。
> 拿不到确切日时标 `null` + 置信度备注，让用户后续校正。

## 3. 女优档案来源

- codeav 影片页通常含女优链接，可解析 `actor` 字段。
- 身高 / 三围 / 生日 / 事务所等个人资料：codeav 未必全有，可补充其他公开资料站，
  或先留 `null`，由社区 PR 完善。

## 4. 图片来源（全热链，不入库）

本仓库**不下载、不存储任何图片**，封面与头像均以 URL 形式直接热链源站图床：

- **封面图**：DMM 图床 `https://pics.dmm.co.jp/<section>/<cid>/<cid><suffix>.jpg`。
  cid 与作品番号存在非统一变换（如 `AKDL→1akdl`、`BAZX→61bazx`），`tools/cover_backfill.py`
  从已有封面反推厂牌模板、再做 HTTP 200 + 图片校验后回填（绝不存坏链）。
- **女优头像**：DMM 写真图床 `https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/<romaji>.jpg`，
  由 `tools/fill_avatars.py` 逐 slug HTTP 校验后写入 `profile.json` 的 `avatar` 字段。
- 渲染层用 `<img referrerpolicy="no-referrer" onerror=...>` 规避防盗链与坏图占位。

> 因为不入库二进制，仓库始终保持轻量、可 PR、符合 GitHub ToS，也规避了成人图片入库的合规风险。

## 5. 合规边界（重要）

- 本仓库只收录**公开索引级元数据**（女优名、番号、发行日、片名），以及**宣传 / 封面肖像的热链 URL**。
- 不收录、不下载、不链接任何露骨内容或盗版资源。
- 图片以外链形式存在，不占用仓库容量、不触发 GitHub 二进制 / ToS 限制。
- 仓库默认 **Private**；确认合规后再改 Public。
- 若某女优 / 作品要求撤下，及时 PR 删除对应 JSON（图片随之外链失效）。

## 6. 与 115 网盘改名的关系

- 本仓库是「情报预处理中心」：`data/` 里的 `title` / `date` / `code` 正是 115 改名所需的原料。
- 改名流程：在仓库查 `code` → 取 `title` + `date` → 套 `av-rename/docs/rules.md` 的
  `YYYY-MM-DD 码 标题·女优[标签].partN.扩展名` 规则 → 用 115 MCP 批量改名。
- 也就是说：**数据先在本仓库集齐，改名只是消费这份数据**，不用每次临时抓网。
