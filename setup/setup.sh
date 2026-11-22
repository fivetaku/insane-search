#!/usr/bin/env bash
# First-run setup for insane-search. Idempotent, non-blocking.
#   setup.sh            -> env checks + update-notifier hook (once). SILENT: no star prompt.
#                          Used by skill / auto-trigger Step 0 (output is discarded).
#                          Every mode also refreshes an already-installed notifier script
#                          when the bundled copy has a newer gptaku-update-check-rev.
#   setup.sh ask        -> same first-run setup, then — iff no star decision is on record —
#                          atomically records an "asked" marker AND prints "STAR_ASK <lang>".
#                          Recording the marker HERE (not via a model follow-up) guarantees
#                          the question is shown at most once per plugin, even if the caller
#                          never reports the answer back. <lang> is a best-effort fallback
#                          language code (ko/ja/en) detected from past Claude session
#                          transcripts — used only when the live conversation has no signal.
#   setup.sh star yes   -> record "yes" and star both repos (own + marketplace hub).
#   setup.sh star no    -> record "no"; star nothing.
#   setup.sh ask autoupdate
#                       -> everything "ask" does, PLUS — iff no auto-update decision is on record
#                          machine-wide and gptaku-plugins auto-update is not already on —
#                          records an "asked" marker and prints "AUTOUPDATE_ASK <lang>".
#                          Opt-in via the extra arg so command files that still call plain
#                          "setup.sh ask" never burn the one-time question without asking it.
#   setup.sh autoupdate yes -> back up known_marketplaces.json, set autoUpdate:true on the
#                          gptaku-plugins entry only (all other keys preserved, atomic write),
#                          record "yes". Prints "AUTOUPDATE_SET <status>".
#   setup.sh autoupdate no  -> record "no"; change nothing.
# The star / auto-update questions are asked by the command flow (AskUserQuestion is Claude-only
# and cannot be issued from bash); this script never stars or edits Claude Code config without
# an explicit "star yes" / "autoupdate yes".
set -uo pipefail

PLUGIN="insane-search"
OWN_REPO="fivetaku/insane-search"
HUB_REPO="fivetaku/gptaku_plugins"

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MARKER_DIR="$HOME/.gptaku-setup"
SETUP_MARKER="$MARKER_DIR/$PLUGIN.json"
STAR_MARKER="$MARKER_DIR/$PLUGIN.star.json"
# Auto-update is a marketplace-level setting, so its decision is machine-wide (not per plugin).
MARKETPLACE_NAME="gptaku-plugins"
AUTOUPDATE_MARKER="$MARKER_DIR/$MARKETPLACE_NAME.autoupdate.json"
KNOWN_MP="$CONFIG_DIR/plugins/known_marketplaces.json"
mkdir -p "$MARKER_DIR"

# --- every run: keep an already-installed notifier script current (silent, cheap) ---
# The hook script is copied into $CONFIG_DIR/scripts/ only on first run, so without this
# existing users would never get notifier fixes. Rules:
#   - only when the script already exists (i.e. we installed the hook earlier);
#   - only when the bundled copy carries a HIGHER "gptaku-update-check-rev" than the
#     installed one (missing rev = 0). Plugins update independently, so an older plugin
#     cache must never downgrade a newer script — plain "content differs" would flip-flop;
#   - atomic (temp file in the same dir + mv); settings.json is never touched here.
notifier_rev() {  # $1 = file -> prints the integer rev, or 0
  r=$(sed -n 's/.*gptaku-update-check-rev: *\([0-9][0-9]*\).*/\1/p' "$1" 2>/dev/null | head -n 1)
  echo "${r:-0}"
}
refresh_notifier() {
  src="$HERE/gptaku-update-check.cjs"
  dst="$CONFIG_DIR/scripts/gptaku-update-check.cjs"
  [ -f "$src" ] && [ -f "$dst" ] || return 0
  cmp -s "$src" "$dst" && return 0
  [ "$(notifier_rev "$src")" -gt "$(notifier_rev "$dst")" ] || return 0
  tmp="$dst.tmp-gptaku-$$"
  if cp -f "$src" "$tmp" 2>/dev/null; then
    mv -f "$tmp" "$dst" 2>/dev/null || rm -f "$tmp" 2>/dev/null
  else
    rm -f "$tmp" 2>/dev/null
  fi
  return 0
}
refresh_notifier >/dev/null 2>&1 || true

# --- detect a fallback UI language from past Claude session transcripts (best-effort) ---
# Counts Hangul / Kana / Latin letters in HUMAN-typed user text only (skips tool results,
# assistant turns and JSON structure, which are ASCII-heavy and would skew to English).
detect_lang() {
  command -v python3 >/dev/null 2>&1 || { echo en; return; }
  python3 - "$CONFIG_DIR/projects" 2>/dev/null <<'PY' || echo en
import sys, os, glob, json
base = sys.argv[1]
try:
    files = sorted(glob.glob(os.path.join(base, "**", "*.jsonl"), recursive=True),
                   key=os.path.getmtime, reverse=True)[:20]
except Exception:
    files = []
# Vote per message (presence of script), not per char — so a few large ASCII
# pastes (code, logs, specs) don't drown out many short typed Korean turns.
ko = ja = en = 0
msgs = 0
def vote(s):
    global ko, ja, en, msgs
    hk = hj = hl = False
    for ch in s:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3: hk = True
        elif 0x3040 <= o <= 0x30FF: hj = True
        elif 65 <= o <= 90 or 97 <= o <= 122: hl = True
    if hk: ko += 1
    elif hj: ja += 1
    elif hl: en += 1
    if hk or hj or hl: msgs += 1
for f in files:
    if msgs >= 400: break
    try:
        fh = open(f, encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for line in fh:
        if msgs >= 400: break
        try:
            m = json.loads(line).get("message")
        except Exception:
            continue
        if not isinstance(m, dict) or m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            vote(c)
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") == "text":
                    vote(part.get("text", ""))
    fh.close()
if ko and ko >= ja and ko >= en: print("ko")
elif ja and ja >= ko and ja >= en: print("ja")
else: print("en")
PY
}

# --- record the star decision (and star the repos on "yes") ---
write_star() {  # $1 = decision (yes|no|asked)
  ts=$(date +%s 2>/dev/null || echo 0)
  printf '{"star_decision":"%s","plugin":"%s","ts":%s}\n' "$1" "$PLUGIN" "$ts" > "$STAR_MARKER"
}

if [ "${1:-}" = "star" ]; then
  DECISION="${2:-no}"
  write_star "$DECISION"
  if [ "$DECISION" = "yes" ] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    for repo in "$OWN_REPO" "$HUB_REPO"; do
      gh api "user/starred/$repo" >/dev/null 2>&1 || gh api -X PUT "user/starred/$repo" >/dev/null 2>&1 || true
    done
  fi
  exit 0
fi

# --- auto-update for the gptaku-plugins marketplace ---
write_autoupdate() {  # $1 = decision (yes|no|asked|already-on)  $2 = result status (optional)
  ts=$(date +%s 2>/dev/null || echo 0)
  printf '{"autoupdate_decision":"%s","result":"%s","marketplace":"%s","ts":%s}\n' \
    "$1" "${2:-}" "$MARKETPLACE_NAME" "$ts" > "$AUTOUPDATE_MARKER"
}

# Prints one word: on | off | missing (no gptaku-plugins entry / no file) | unknown (no python3).
# Same precedence as Claude Code: an autoUpdate declared in user settings
# (extraKnownMarketplaces) wins over the known_marketplaces.json entry.
autoupdate_state() {
  command -v python3 >/dev/null 2>&1 || { echo unknown; return; }
  python3 - "$KNOWN_MP" "$CONFIG_DIR/settings.json" "$MARKETPLACE_NAME" 2>/dev/null <<'PY' || echo unknown
import json, sys
known_p, settings_p, name = sys.argv[1:4]
def load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
k = load(known_p)
if not isinstance(k, dict) or not isinstance(k.get(name), dict):
    print("missing"); sys.exit(0)
s = load(settings_p) or {}
d = (s.get("extraKnownMarketplaces") or {}).get(name) if isinstance(s, dict) else None
if isinstance(d, dict) and isinstance(d.get("autoUpdate"), bool):
    print("on" if d["autoUpdate"] else "off"); sys.exit(0)
print("on" if k[name].get("autoUpdate") is True else "off")
PY
}

if [ "${1:-}" = "autoupdate" ]; then
  DECISION="${2:-no}"
  if [ "$DECISION" != "yes" ]; then
    write_autoupdate "no"
    echo "AUTOUPDATE_SET skipped"
    exit 0
  fi
  STATUS="error"
  if command -v python3 >/dev/null 2>&1; then
    STATUS=$(python3 - "$KNOWN_MP" "$CONFIG_DIR/settings.json" "$MARKETPLACE_NAME" 2>/dev/null <<'PY' || echo error
import json, os, shutil, sys, tempfile, time
known_p, settings_p, name = sys.argv[1:4]
try:
    with open(known_p, encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print("missing"); sys.exit(0)
if not isinstance(data, dict) or not isinstance(data.get(name), dict):
    print("missing"); sys.exit(0)
# A user-settings declaration overrides the JSON (Claude Code re-syncs it on start).
try:
    with open(settings_p, encoding="utf-8") as f:
        s = json.load(f)
    d = (s.get("extraKnownMarketplaces") or {}).get(name)
    if isinstance(d, dict) and d.get("autoUpdate") is False:
        print("overridden-by-settings"); sys.exit(0)
except Exception:
    pass
if data[name].get("autoUpdate") is True:
    print("already"); sys.exit(0)
backup = "%s.bak-gptaku-autoupdate-%d" % (known_p, int(time.time()))
shutil.copy2(known_p, backup)
data[name]["autoUpdate"] = True          # only this key on only this entry changes
d = os.path.dirname(known_p) or "."
mode = os.stat(known_p).st_mode & 0o777
fd, tmp = tempfile.mkstemp(prefix=".known_marketplaces.", suffix=".tmp", dir=d)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, known_p)             # atomic on the same filesystem
except Exception:
    try: os.unlink(tmp)
    except Exception: pass
    raise
print("on")
PY
)
  fi
  write_autoupdate "yes" "$STATUS"
  echo "AUTOUPDATE_SET $STATUS"
  exit 0
fi

# --- first-run env checks + update-notifier hook (silent, once per machine) ---
if [ ! -f "$SETUP_MARKER" ]; then
  HAVE_NODE=0; command -v node >/dev/null 2>&1 && HAVE_NODE=1
  if [ "$HAVE_NODE" = "1" ]; then
    SCRIPTS_DIR="$CONFIG_DIR/scripts"
    mkdir -p "$SCRIPTS_DIR"
    [ -f "$HERE/gptaku-update-check.cjs" ] && cp -f "$HERE/gptaku-update-check.cjs" "$SCRIPTS_DIR/gptaku-update-check.cjs" 2>/dev/null
    CLAUDE_CONFIG_DIR="$CONFIG_DIR" node -e '
      const fs=require("fs"),path=require("path"),os=require("os");
      const cfg=process.env.CLAUDE_CONFIG_DIR||path.join(os.homedir(),".claude");
      const p=path.join(cfg,"settings.json");
      // settings.json이 존재하는데 파싱이 안 되면(손상/JSONC) 절대 덮어쓰지 않고 포기한다.
      // 빈 객체로 재작성하면 사용자 설정 전체가 증발한다 (2026-08-23 ddiring 리뷰 High).
      let d={};
      try{
        const raw=fs.readFileSync(p,"utf8");
        if(raw.trim()) d=JSON.parse(raw);
      }catch(e){
        if(e && e.code==="ENOENT") d={};
        else process.exit(0);
      }
      if(typeof d!=="object"||d===null||Array.isArray(d)) process.exit(0);
      d.hooks=d.hooks||{};
      const ss=d.hooks.SessionStart=Array.isArray(d.hooks.SessionStart)?d.hooks.SessionStart:[];
      const has=ss.some(e=>((e&&e.hooks)||[]).some(h=>String((h&&h.command)||"").includes("gptaku-update-check")));
      if(!has){
        const cmd="node "+JSON.stringify(path.join(cfg,"scripts","gptaku-update-check.cjs"));
        ss.push({matcher:"*",hooks:[{type:"command",command:cmd,timeout:5}]});
        // 임시파일 + rename으로 원자적 쓰기(부분 쓰기로 인한 파손 방지)
        try{
          const tmp=p+".tmp-gptaku-"+process.pid;
          fs.writeFileSync(tmp,JSON.stringify(d,null,2));
          fs.renameSync(tmp,p);
        }catch{}
      }
    ' >/dev/null 2>&1 || true
  fi
  ts=$(date +%s 2>/dev/null || echo 0)
  printf '{"setup":true,"plugin":"%s","ts":%s}\n' "$PLUGIN" "$ts" > "$SETUP_MARKER"
fi

# --- ask mode: emit the star prompt EXACTLY ONCE, recording it deterministically ---
# Only the command flow passes "ask". Bare / silent skill invocations never reach here,
# so they neither prompt nor record — the prompt is shown at most once, by a command,
# and the "asked" marker is written by bash regardless of any model follow-up.
if [ "${1:-}" = "ask" ] && [ ! -f "$STAR_MARKER" ]; then
  write_star "asked"
  echo "STAR_ASK $(detect_lang)"
fi

# --- ask autoupdate: emit the auto-update prompt at most once per machine ---
# Only when the gptaku-plugins entry exists and auto-update is not already on;
# "missing"/"unknown" record nothing so a later run (after a real marketplace add) can still ask.
if [ "${1:-}" = "ask" ] && [ "${2:-}" = "autoupdate" ] && [ ! -f "$AUTOUPDATE_MARKER" ]; then
  case "$(autoupdate_state)" in
    off) write_autoupdate "asked"; echo "AUTOUPDATE_ASK $(detect_lang)" ;;
    on)  write_autoupdate "already-on" ;;
  esac
fi
exit 0
