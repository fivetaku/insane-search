[English](README.md) | [한국어](README.ko.md) | 中文 | [日本語](README.ja.md) | [Español](README.es.md)

<div align="center">

# insane-search

**Impossible is nothing. 只要是公开页面，insane-search 终会突破。**

为 Claude Code 打造的抗封锁公开页面阅读器。无需 API 密钥，无需代理配置。

<p>
  <a href="https://docs.anthropic.com/en/docs/claude-code"><img src="https://img.shields.io/badge/platform-Claude_Code-D97757?logo=claude" alt="Claude Code"></a>
  <img src="https://img.shields.io/badge/API_key-not_required-3FB950" alt="No API key">
  <a href="https://github.com/fivetaku/gptaku_plugins"><img src="https://img.shields.io/badge/part_of-gptaku--plugins-6E56CF" alt="part of gptaku-plugins"></a>
  <a href="https://github.com/fivetaku/insane-search/stargazers"><img src="https://img.shields.io/github/stars/fivetaku/insane-search?style=flat&color=F0B72F" alt="stars"></a>
</p>

<!-- Hero — cinematic key-art: a blocked site (403 / CAPTCHA / WAF) shatters as
     insane-search breaks through and returns real public content with its source. -->
<img src="assets/hero.png" width="860" alt="电影感分屏：左侧是被 403 Forbidden、CAPTCHA、WAF 拦截的站点，画面从中间碎裂，右侧 insane-search 突破而入，无需 API 密钥取回 @claudeai（Claude Code Plugins）的真实公开帖文及其来源。">

</div>

---

## ⚡ 安装

```bash
/plugin marketplace add https://github.com/fivetaku/gptaku_plugins.git
/plugin install insane-search@gptaku-plugins
/reload-plugins
```

无需记任何命令。像平常一样向 Claude Code 提问即可——一旦抓取被拦截，insane-search 就会自动介入。

## 💬 试试看

正常提问就行——抓取被拦时 insane-search 会自动启动：

> *"找出 Reddit 上大家对 Claude Code 的看法，并总结热门讨论。"*
> *"在 X 上搜索关于 insane-search 的帖子。"*
> *"总结这个 YouTube 视频。"*

**预期效果：** Claude 通过各站点的公开路径——Reddit 的订阅源、X 的 oEmbed、YouTube 的字幕——在无需登录、无需 API 密钥的情况下取回可用文本；而没有该插件时，同样的请求只会得到 *"我无法访问"*。

## 🌐 支持的平台

**X · Reddit · YouTube · Hacker News · Naver · Coupang · LinkedIn · Medium · Substack · arXiv · GitHub · Stack Overflow · Bluesky · Mastodon** ——以及任何拥有公开页面、订阅源或 `/rss` 的站点。完整平台列表与方法 → [PLATFORMS.md](PLATFORMS.md)。

## ⚙️ 为什么能突破

- **逐级升级，从不预设放弃** —— 公开 API 阅读器 → 聚合网关 → TLS 指纹伪装 → 真实无头浏览器，逐条路径尝试直到有一条成功。
- **看起来像真人** —— 不只是替换 User-Agent，而是构建完整的浏览器身份（真实 TLS 指纹、Cookie 预热、Referer 链）。
- **找出隐藏 API** —— 监听真实浏览器的网络流量，复用站点自身的内部 JSON。
- **零配置** —— 首次使用时自动安装所需工具（`curl_cffi`、`yt-dlp` 等）。无需 API 密钥，无需注册。

## 🆚 默认 Claude Code vs `+ insane-search`

| 当你遇到… | 仅 Claude Code | `+ insane-search` |
| :--- | :--- | :--- |
| `403` / WAF 拦截的页面 | ✖ 放弃 | ✓ 持续升级直到有一条路径成功 |
| 平台内容（X、Reddit、HN） | ✖ 常被拦或为空 | ✓ 公开 API 阅读器 + 聚合源 |
| 反爬 / CAPTCHA 挑战 | ✖ 停止 | ✓ TLS 伪装，必要时真实无头浏览器 |
| 媒体页面（YouTube 等 1,800+ 站） | ✖ 无字幕 | ✓ `yt-dlp` 元数据 + 字幕 |
| 缺少工具（`curl_cffi`、`yt-dlp`） | — | ✓ 首次使用自动安装 |
| API 密钥 / 注册 | — | ✓ 不需要 |
| **登录墙或付费墙** | ✖ | ✖ **到此为止，并如实说明**（见 Boundaries） |

真正拉开差距的是默认抓取做不到的那一行：**它会持续尝试公开路径，直到有一条成功。**

## ✨ 刚刚发生了什么

| 没有它 | 有 insane-search |
| :--- | :--- |
| 普通抓取撞上 `403`，Claude 说读不了 | 插件选一条公开访问路径，取回可用文本 |
| 你得手动试镜像、存档、移动版 URL | 回退路径自动升级，且全程只走公开渠道 |
| 被拦的页面就是死胡同 | 元数据与结构化数据仍能产出标题、价格、摘要 |

## 🔁 工作原理

<img src="assets/pipeline.png" width="860" alt="Phase 0→3 升级管线：被拦截的 URL 依次经过官方公开端点 → 轻量探测 → TLS 伪装 → 真实无头浏览器，直到有一条返回干净的公开内容；遇到登录或付费墙则以 'authentication required' 停止。每个响应都会扫描 OGP / JSON-LD。">

<details>
<summary><strong>Phase 0→3 自适应调度器 —— 细节</strong></summary>

每个阶段仅在上一阶段失败或检测到拦截信号时才执行：

- **Phase 0** —— 通用链路无法自行发现的官方公开端点（平台 API、订阅源）
- **Phase 1** —— 轻量探测：公开 API 阅读器、聚合网关、移动版 / `.json` / `/rss` URL 变体
- **Phase 2** —— TLS 指纹伪装（curl_cffi：safari → chrome → firefox）+ 完整浏览器身份
- **Phase 3** —— 真实无头浏览器，同时暴露站点内部使用的公开 JSON API
- **Exit** —— 检测到登录或付费墙：如实报告 *"authentication required"*，绝不伪装

每个响应还会扫描 OGP / JSON-LD，因此即便是残缺页面也能产出标题、摘要和价格。
</details>

## 🔒 边界（Boundaries）

insane-search 是**公开内容的阅读器**，不是绕过身份验证的工具。

- 触达公开页面、公开 API、订阅源、存档以及浏览器公开响应中可获取的内容。
- **在登录与付费墙前停止** —— 报告 `authentication required`，而不是设法攻破。
- 绝不代你登录，绝不存储或传输凭据。
- 所有路径只用无需认证的公开端点和标准的、有据可查的技术。

## 许可证

MIT

---

<div align="center">

**[gptaku-plugins](https://github.com/fivetaku/gptaku_plugins) 的一部分** —— 突破其他一切止步之墙的 Claude Code 插件集。

</div>
