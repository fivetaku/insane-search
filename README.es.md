[English](README.md) | [한국어](README.ko.md) | [中文](README.zh.md) | [日本語](README.ja.md) | Español

<div align="center">

# insane-search

**Impossible is nothing. Si es público, insane-search acaba entrando.**

Un lector de páginas públicas resistente al bloqueo, para Claude Code. Sin claves de API, sin configurar proxies.

<p>
  <a href="https://docs.anthropic.com/en/docs/claude-code"><img src="https://img.shields.io/badge/platform-Claude_Code-D97757?logo=claude" alt="Claude Code"></a>
  <img src="https://img.shields.io/badge/API_key-not_required-3FB950" alt="No API key">
  <a href="https://github.com/fivetaku/gptaku_plugins"><img src="https://img.shields.io/badge/part_of-gptaku--plugins-6E56CF" alt="part of gptaku-plugins"></a>
  <a href="https://github.com/fivetaku/insane-search/stargazers"><img src="https://img.shields.io/github/stars/fivetaku/insane-search?style=flat&color=F0B72F" alt="stars"></a>
</p>

<!-- Hero — cinematic key-art: a blocked site (403 / CAPTCHA / WAF) shatters as
     insane-search breaks through and returns real public content with its source. -->
<img src="assets/hero.png" width="860" alt="División cinematográfica: a la izquierda un sitio bloqueado muestra 403 Forbidden, un CAPTCHA y un muro WAF; se rompe por el centro mientras insane-search atraviesa por la derecha y devuelve una publicación pública real de @claudeai (Claude Code Plugins) con su fuente, sin clave de API.">

</div>

---

## ⚡ Instalación

```bash
/plugin marketplace add https://github.com/fivetaku/gptaku_plugins.git
/plugin install insane-search@gptaku-plugins
/reload-plugins
```

No hay comandos que aprender. Habla con Claude Code como siempre: insane-search entra en acción en cuanto una petición se bloquea.

## 💬 Pruébalo

Solo pídelo con normalidad: insane-search se activa cuando algo se bloquea:

> *"Busca qué dice la gente sobre Claude Code en Reddit y resume los hilos más populares."*
> *"Busca en X publicaciones sobre insane-search."*
> *"Resume este vídeo de YouTube."*

**Resultado esperado:** Claude llega a la ruta pública de cada sitio —el feed de Reddit, X vía oEmbed, los subtítulos de YouTube— sin inicio de sesión ni clave de API, y devuelve texto utilizable, allí donde la misma petición respondería *"no puedo acceder a eso"* sin el plugin.

## 🌐 Funciona en

**X · Reddit · YouTube · Hacker News · Naver · Coupang · LinkedIn · Medium · Substack · arXiv · GitHub · Stack Overflow · Bluesky · Mastodon** —además de cualquier sitio con una página pública, un feed o `/rss`. Lista completa de plataformas y métodos → [PLATFORMS.md](PLATFORMS.md).

## ⚙️ Por qué lo consigue

- **Escala, nunca prejuzga** —lectores de API públicas → pasarelas de sindicación → suplantación TLS → un navegador headless real, probando cada ruta hasta que una funciona.
- **Parece humano** —construye una identidad de navegador completa (huella TLS real, calentamiento de cookies, cadena de referer), no solo un User-Agent cambiado.
- **Encuentra APIs ocultas** —observa el tráfico de red del navegador real y reutiliza el JSON interno del propio sitio.
- **Cero configuración** —instala lo que necesita (`curl_cffi`, `yt-dlp`, …) en el primer uso. Sin claves de API, sin registro.

## 🆚 Claude Code por defecto vs `+ insane-search`

| Cuando te topas con… | Claude Code solo | `+ insane-search` |
| :--- | :--- | :--- |
| Una página con `403` / bloqueada por WAF | ✖ se rinde | ✓ escala hasta que una ruta entra |
| Contenido de plataformas (X, Reddit, HN) | ✖ a menudo bloqueado o vacío | ✓ lectores de API públicas + sindicación |
| Un reto anti-bot / CAPTCHA | ✖ se detiene | ✓ suplantación TLS y, si hace falta, navegador headless real |
| Una página multimedia (YouTube, 1.800+ sitios) | ✖ sin transcripción | ✓ metadatos `yt-dlp` + subtítulos |
| Herramientas que faltan (`curl_cffi`, `yt-dlp`) | — | ✓ se instalan solas en el primer uso |
| Claves de API / registro | — | ✓ ninguno |
| Un **muro de login o de pago** | ✖ | ✖ **se detiene aquí, y lo dice** (ver Límites) |

La fila que marca la diferencia es lo único que el fetch por defecto no puede hacer: **sigue probando rutas públicas hasta que una funciona.**

## ✨ Qué acaba de pasar

| Sin él | Con insane-search |
| :--- | :--- |
| Un fetch normal choca con `403` y Claude dice que no puede leer la página | El plugin elige una ruta de acceso público y devuelve texto utilizable |
| Pruebas a mano espejos, archivos, URLs móviles | Los fallbacks escalan solos, siempre por rutas públicas |
| Una página bloqueada es un callejón sin salida | Los metadatos y datos estructurados aún dan títulos, precios y resúmenes |

## 🔁 Cómo funciona

<img src="assets/pipeline.png" width="860" alt="Pipeline de escalada Phase 0→3: una URL bloqueada pasa por endpoints públicos oficiales → sondas ligeras → suplantación TLS → un navegador headless real hasta que una devuelve contenido público limpio; ante un login o muro de pago sale con 'authentication required'. Cada respuesta se escanea en busca de OGP / JSON-LD.">

<details>
<summary><strong>Planificador adaptativo Phase 0→3 — detalles</strong></summary>

Cada fase se ejecuta solo si la anterior falla o detecta una señal de bloqueo:

- **Phase 0** — endpoints públicos oficiales (APIs de plataforma, feeds) que la cadena genérica no puede descubrir por sí sola
- **Phase 1** — sondas ligeras: lectores de API públicas, pasarelas de sindicación, variantes de URL móvil / `.json` / `/rss`
- **Phase 2** — suplantación TLS (curl_cffi: safari → chrome → firefox) con una identidad de navegador completa
- **Phase 3** — un navegador headless real, que además saca a la luz las APIs JSON públicas que un sitio usa internamente
- **Exit** — se detecta un login o muro de pago: informa *"authentication required"* en lugar de fingir

Cada respuesta también se escanea en busca de OGP / JSON-LD, así que incluso las páginas parciales dan títulos, resúmenes y precios.
</details>

## 🔒 Límites (Boundaries)

insane-search es un **lector de contenido público**, no una forma de saltarse la autenticación.

- Alcanza lo disponible a través de páginas públicas, APIs públicas, feeds, archivos y las respuestas públicas de un navegador.
- **Se detiene en logins y muros de pago** —informa `authentication required` en vez de intentar vencerlos.
- Nunca inicia sesión por ti y nunca almacena ni transmite credenciales.
- Todas las rutas usan endpoints públicos sin autenticación y técnicas estándar y documentadas.

## Licencia

MIT

---

<div align="center">

**Parte de [gptaku-plugins](https://github.com/fivetaku/gptaku_plugins)** — plugins de Claude Code que atraviesan los muros donde todo lo demás se detiene.

</div>
