[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | 日本語 | [Español](README.es.md)

<div align="center">

# insane-search

**Impossible is nothing. 公開ページなら、insane-search はいずれ突破する。**

Claude Code 向けの、ブロックに強い公開ページリーダー。API キーもプロキシ設定も不要。

<p>
  <a href="https://docs.anthropic.com/en/docs/claude-code"><img src="https://img.shields.io/badge/platform-Claude_Code-D97757?logo=claude" alt="Claude Code"></a>
  <img src="https://img.shields.io/badge/API_key-not_required-3FB950" alt="No API key">
  <a href="https://github.com/fivetaku/gptaku_plugins"><img src="https://img.shields.io/badge/part_of-gptaku--plugins-6E56CF" alt="part of gptaku-plugins"></a>
  <a href="https://github.com/fivetaku/insane-search/stargazers"><img src="https://img.shields.io/github/stars/fivetaku/insane-search?style=flat&color=F0B72F" alt="stars"></a>
</p>

<!-- Hero — cinematic key-art: a blocked site (403 / CAPTCHA / WAF) shatters as
     insane-search breaks through and returns real public content with its source. -->
<img src="assets/hero.png" width="860" alt="シネマティックな分割画面：左は 403 Forbidden・CAPTCHA・WAF でブロックされたサイト。中央から砕け、右で insane-search が突破し、API キーなしで @claudeai（Claude Code Plugins）の実際の公開ポストを出典付きで取得する。">

</div>

---

## ⚡ インストール

```bash
/plugin marketplace add https://github.com/fivetaku/gptaku_plugins.git
/plugin install insane-search@gptaku-plugins
/reload-plugins
```

覚えるコマンドはありません。いつも通り Claude Code に話しかければ、フェッチがブロックされた瞬間に insane-search が割り込みます。

## 💬 使ってみる

普通に頼むだけ——ブロックされた瞬間に insane-search が動きます：

> *"Reddit で Claude Code の反応を探して、人気スレッドを要約して。"*
> *"X で insane-search に関する投稿を検索して。"*
> *"この YouTube 動画を要約して。"*

**期待される動作：** Claude が各サイトの公開ルート——Reddit のフィード、X の oEmbed、YouTube の字幕——にログインも API キーもなしで到達し、使えるテキストを返します。プラグインがなければ同じ依頼に *"アクセスできません"* が返るところを。

## 🌐 対応サイト

**X · Reddit · YouTube · Hacker News · Naver · Coupang · LinkedIn · Medium · Substack · arXiv · GitHub · Stack Overflow · Bluesky · Mastodon** ——さらに公開ページ・フィード・`/rss` を持つあらゆるサイト。全プラットフォーム一覧と手法 → [PLATFORMS.md](PLATFORMS.md)。

## ⚙️ なぜ突破できるのか

- **諦めず段階を上げる** —— 公開 API リーダー → シンジケーションゲートウェイ → TLS なりすまし → 本物のヘッドレスブラウザと、いずれか一つが通るまで各ルートを試す。
- **人間に見える** —— User-Agent を差し替えるだけでなく、完全なブラウザ ID（本物の TLS フィンガープリント、Cookie ウォーミング、Referer チェーン）を構築する。
- **隠れた API を見つける** —— 本物のブラウザのネットワーク通信を観察し、サイト自身の内部 JSON を再利用する。
- **セットアップ不要** —— 必要なツール（`curl_cffi`、`yt-dlp` など）を初回利用時に自動インストール。API キーも登録も不要。

## 🆚 デフォルト Claude Code vs `+ insane-search`

| こんなとき… | Claude Code 単体 | `+ insane-search` |
| :--- | :--- | :--- |
| `403` / WAF でブロックされたページ | ✖ あきらめる | ✓ 通るまで段階を上げる |
| プラットフォームのコンテンツ（X、Reddit、HN） | ✖ よくブロック・空応答 | ✓ 公開 API リーダー + シンジケーション |
| アンチボット / CAPTCHA チャレンジ | ✖ 停止 | ✓ TLS なりすまし、ダメなら本物のヘッドレスブラウザ |
| メディアページ（YouTube など 1,800+ サイト） | ✖ 字幕なし | ✓ `yt-dlp` メタデータ + 字幕 |
| ツール未導入（`curl_cffi`、`yt-dlp`） | — | ✓ 初回利用時に自動インストール |
| API キー / 登録 | — | ✓ 不要 |
| **ログインウォール / ペイウォール** | ✖ | ✖ **ここで止まり、そう伝える**（Boundaries 参照） |

差を生むのは、デフォルトのフェッチにできない唯一のこと：**通るまで公開ルートを試し続ける。**

## ✨ 何が起きたのか

| なし | insane-search あり |
| :--- | :--- |
| 普通のフェッチが `403` に当たり、Claude が読めないと言う | プラグインが公開アクセスルートを選び、使えるテキストを返す |
| ミラー・アーカイブ・モバイル URL を手で試す羽目に | フォールバックが自動で段階を上げる、しかも公開ルートのみ |
| ブロックされたページは行き止まり | メタデータと構造化データからタイトル・価格・要約は得られる |

## 🔁 仕組み

<img src="assets/pipeline.png" width="860" alt="Phase 0→3 エスカレーションパイプライン：ブロックされた URL が公式公開エンドポイント → 軽量プローブ → TLS なりすまし → 本物のヘッドレスブラウザを順に通り、いずれかがクリーンな公開コンテンツを返すまで進む。ログインやペイウォールなら 'authentication required' で停止。すべての応答は OGP / JSON-LD でスキャンされる。">

<details>
<summary><strong>Phase 0→3 アダプティブスケジューラ —— 詳細</strong></summary>

各フェーズは、前のフェーズが失敗するかブロック信号を検知したときだけ実行されます：

- **Phase 0** —— 汎用チェーンが自力で見つけられない公式公開エンドポイント（プラットフォーム API、フィード）
- **Phase 1** —— 軽量プローブ：公開 API リーダー、シンジケーションゲートウェイ、モバイル / `.json` / `/rss` の URL バリアント
- **Phase 2** —— TLS なりすまし（curl_cffi：safari → chrome → firefox）+ 完全なブラウザ ID
- **Phase 3** —— 本物のヘッドレスブラウザ。サイトが内部で使う公開 JSON API も表面化させる
- **Exit** —— ログインやペイウォールを検知：装わず *"authentication required"* と報告する

すべての応答は OGP / JSON-LD でもスキャンされるため、断片的なページでもタイトル・要約・価格は得られます。
</details>

## 🔒 境界（Boundaries）

insane-search は**公開コンテンツのリーダー**であり、認証を回避する手段ではありません。

- 公開ページ・公開 API・フィード・アーカイブ・ブラウザの公開応答で届く範囲に到達します。
- **ログインとペイウォールで止まります** —— 突破しようとせず `authentication required` と報告します。
- あなたの代わりにログインせず、認証情報を保存も送信もしません。
- すべてのルートは認証不要の公開エンドポイントと、標準的で文書化された手法のみを使います。

## ライセンス

MIT

---

<div align="center">

**[gptaku-plugins](https://github.com/fivetaku/gptaku_plugins) の一部** —— 他のすべてが止まる壁を突き破る Claude Code プラグイン集。

</div>
