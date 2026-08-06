# Disclaimer & Acceptable Use — insane-search

`insane-search` is part of the [gptaku-plugins](https://github.com/fivetaku/gptaku_plugins)
collection and is distributed under the [MIT License](./LICENSE).
Copyright (c) 2026 fivetaku.

This document does not modify the MIT License; it clarifies the author's intent
and the responsibilities of anyone who uses, integrates, or redistributes this
software. Where this document and the LICENSE appear to differ, the LICENSE
governs the legal grant and the disclaimer of warranty and liability.

## 1. No warranty

The software is provided **"AS IS"**, without warranty of any kind, express or
implied, including but not limited to the warranties of merchantability, fitness
for a particular purpose, and non-infringement. The author does not guarantee
that the software is correct, complete, reliable, secure, available, or suitable
for any particular purpose, and does not guarantee any specific result from its
use.

## 2. Limitation of liability

In no event shall the author or copyright holder be liable for any claim,
damages, loss, or other liability — whether in an action of contract, tort
(including negligence), or otherwise — arising from, out of, or in connection
with the software or the use of or other dealings in the software. You use the
software entirely at your own risk.

## 3. Intended use and dual-use nature

`insane-search` is a general-purpose developer tool. Like most general-purpose tools, it
is inherently dual-use: it is published for legitimate, lawful, and authorized
purposes, and the author has no ability to monitor, approve, or control how
third parties actually use it.

## 4. No affiliation or endorsement

The author is **not affiliated with**, and does **not** endorse, sponsor,
support, or take responsibility for, any third-party project that derives from,
integrates, forks, embeds, redistributes, or otherwise builds upon this
software. The MIT License permits such downstream use without the author's
review or approval. The existence of any downstream project — including security,
offensive-security, or automation tooling — does **not** imply any relationship
with, contribution by, or approval from the author, and any responsibility or
liability for such a project rests entirely with its own authors and users.

## 5. Your responsibility

You are solely responsible for how you use this software, including full
compliance with all applicable laws and regulations and with the terms of
service of any system, network, platform, or website you interact with through
it. You must obtain proper authorization before accessing, testing, or
interacting with any system you do not own or are not explicitly permitted to
use. Misuse — including any unlawful or unauthorized activity — is solely your
responsibility.

## 6. Scope of access (specific to insane-search)

`insane-search` reads **publicly available content**. To reach pages that block
generic HTTP clients, it may present ordinary-browser characteristics — for
example real TLS fingerprints via `curl_cffi`, standard request headers, or a
real headless browser. It does **not** log in on your behalf, handle or store
credentials, or attempt to defeat authentication: by design it stops at logins
and paywalls and reports `authentication required`.

Making automated requests resemble an ordinary browser is a common, dual-use
technique. Whether you are **authorized** to access a given site by automated
means — and your compliance with that site's Terms of Service, `robots.txt`,
rate limits, and all applicable law — is **solely your responsibility**. Do not
use `insane-search`, or any derivative of it, against systems you do not own or
are not permitted to access. Any such use is solely the responsibility of the
person doing so.
