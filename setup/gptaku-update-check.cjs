#!/usr/bin/env node
'use strict';
/*
 * gptaku-plugins — SessionStart update notifier (shared across all plugins).
 *
 * Mirrors oh-my-claudecode's approach, adapted for a git-submodule marketplace:
 *   - "latest version" comes from the marketplace git remote, not npm.
 *   - The expensive part (network: git ls-remote) is cached 24h.
 *   - The local marketplace HEAD is read fresh every run, so once the user
 *     pulls + restarts the notice disappears immediately (no stale positives).
 *   - All gptaku plugins ship this same hook; an exclusive per-session lock
 *     ensures only the FIRST plugin to fire does the work — the rest are no-ops.
 *
 * A hook must never break the session: every path exits 0 with valid JSON.
 *
 * Canonical source: shared/update-hook/ in the gptaku_plugins repo.
 * Do not edit per-plugin copies; edit the canonical file and re-run the deploy.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');

const HOME = os.homedir();
const CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(HOME, '.claude');
const MARKETPLACE = path.join(CONFIG_DIR, 'plugins', 'marketplaces', 'gptaku-plugins');
const STATE_DIR = path.join(CONFIG_DIR, '.gptaku-update');
const CACHE_FILE = path.join(STATE_DIR, 'check-cache.json');
const CACHE_MS = 24 * 60 * 60 * 1000;

function emitSilent() {
  process.stdout.write(JSON.stringify({ continue: true, suppressOutput: true }));
  process.exit(0);
}

function emitNotice(text) {
  process.stdout.write(JSON.stringify({
    continue: true,
    hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: text },
  }));
  process.exit(0);
}

function git(args, timeoutMs) {
  return execFileSync('git', ['-C', MARKETPLACE, ...args], {
    encoding: 'utf-8',
    timeout: timeoutMs || 4000,
    stdio: ['ignore', 'pipe', 'ignore'],
  }).trim();
}

function readSessionId() {
  try {
    const raw = fs.readFileSync(0, 'utf-8');
    if (!raw) return '';
    const j = JSON.parse(raw);
    return j.session_id || j.sessionId || '';
  } catch {
    return '';
  }
}

// Returns true if THIS process claimed the session (i.e. it should do the work).
// Returns false if another plugin already claimed it (we should stay silent).
function claimSession(sessionId) {
  if (!sessionId) return true; // no id → can't dedup; just proceed
  const safe = sessionId.replace(/[^A-Za-z0-9_-]/g, '');
  const lock = path.join(STATE_DIR, 'session-' + safe + '.lock');
  try {
    fs.writeFileSync(lock, String(Date.now()), { flag: 'wx' }); // atomic exclusive create
    cleanupStaleLocks();
    return true;
  } catch (e) {
    if (e && e.code === 'EEXIST') return false; // someone else got here first
    return true; // unexpected error → don't block the notice
  }
}

function cleanupStaleLocks() {
  try {
    const cutoff = Date.now() - CACHE_MS;
    for (const f of fs.readdirSync(STATE_DIR)) {
      if (!f.startsWith('session-')) continue;
      const fp = path.join(STATE_DIR, f);
      try { if (fs.statSync(fp).mtimeMs < cutoff) fs.unlinkSync(fp); } catch {}
    }
  } catch {}
}

function getRemoteShaCached() {
  // Fresh from cache if within TTL.
  try {
    if (fs.existsSync(CACHE_FILE)) {
      const c = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf-8'));
      if (c && c.timestamp && (Date.now() - c.timestamp) < CACHE_MS && c.remoteSha) {
        return c.remoteSha;
      }
    }
  } catch {}
  // Otherwise hit the network (branch-agnostic: remote default HEAD).
  try {
    const out = git(['ls-remote', 'origin', 'HEAD'], 2500);
    const sha = (out.split(/\s+/)[0] || '').trim();
    if (sha) {
      try { fs.writeFileSync(CACHE_FILE, JSON.stringify({ timestamp: Date.now(), remoteSha: sha })); } catch {}
      return sha;
    }
  } catch {}
  return '';
}

try {
  const sessionId = readSessionId();

  try { fs.mkdirSync(STATE_DIR, { recursive: true }); } catch {}

  if (!claimSession(sessionId)) emitSilent();

  if (!fs.existsSync(path.join(MARKETPLACE, '.git'))) emitSilent(); // not a git marketplace install

  let localSha = '';
  try { localSha = git(['rev-parse', 'HEAD']); } catch {}
  if (!localSha) emitSilent();

  const remoteSha = getRemoteShaCached();

  if (remoteSha && localSha && remoteSha !== localSha) {
    const lo = localSha.slice(0, 7);
    const re = remoteSha.slice(0, 7);
    emitNotice(
      '[GPTAKU 플러그인 업데이트 있음] gptaku-plugins 마켓플레이스에 새 커밋이 있습니다 ' +
      '(로컬 ' + lo + ' → 리모트 ' + re + '). ' +
      '/plugin 메뉴에서 gptaku-plugins 마켓플레이스를 업데이트하거나, ' +
      '마켓플레이스 클론에서 git pull 후 Claude Code를 재시작하세요.'
    );
  }

  emitSilent();
} catch {
  emitSilent();
}
