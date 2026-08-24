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

## 4. 图片来源

- 封面图：codeav / DMM 影片页的 `og:image` 或海报图。注意 DMM 新站是 JS 渲染，
  纯静态抓取拿不到，需用无头浏览器（Playwright）渲染后取图——见 `scripts/fetch_images.py` 的 TODO。
  入库路径：`site/assets/img/<女优名>/<番号>.jpg`。
- 头像：女优官方 / 宣传图，入库路径：`site/assets/img/<女优名>/avatar.jpg`。
  务必只用**宣传 / 封面类肖像**，不含露骨内容。

## 5. 合规边界（重要）

- 本仓库只收录**公开索引级元数据**（女优名、番号、发行日、片名），以及**宣传 / 封面肖像**。
- 不收录、不链接任何露骨内容或盗版资源下载。
- 图片入库请遵守 GitHub ToS（单文件 < 100MB，仓库 < 1GB）；女优头像 / 封面都是小图，无压力。
- 仓库默认 **Private**；确认合规后再改 Public。
- 若某女优 / 作品要求撤下，及时 PR 删除对应 JSON 与图片。

## 6. 与 115 网盘改名的关系

- 本仓库是「情报预处理中心」：`data/` 里的 `title` / `date` / `code` 正是 115 改名所需的原料。
- 改名流程：在仓库查 `code` → 取 `title` + `date` → 套 `av-rename/docs/rules.md` 的
  `YYYY-MM-DD 码 标题·女优[标签].partN.扩展名` 规则 → 用 115 MCP 批量改名。
- 也就是说：**数据先在本仓库集齐，改名只是消费这份数据**，不用每次临时抓网。
