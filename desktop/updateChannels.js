/**
 * Phase 5 — update channel soft-check (no auto-download/install).
 *
 * Env: SSAK_UPDATE_FEED — JSON feed URL (unset → "업데이트 서버 미구성").
 * Channel model: stable | beta. Git branch ≠ product channel (see UPDATE_CHANNELS.md).
 */

'use strict';

const CHANNELS = Object.freeze(['stable', 'beta']);
const DEFAULT_CHANNEL = 'stable';

/** Env var name for the update feed URL (documented; signing/CDN = BLOCKED_EXTERNAL). */
const UPDATE_FEED_ENV = 'SSAK_UPDATE_FEED';

/**
 * @param {string|undefined|null} raw
 * @returns {'stable'|'beta'}
 */
function normalizeChannel(raw) {
  const c = String(raw || DEFAULT_CHANNEL).trim().toLowerCase();
  if (CHANNELS.includes(c)) return /** @type {'stable'|'beta'} */ (c);
  return DEFAULT_CHANNEL;
}

/**
 * Resolve feed URL from env (or explicit override). Empty → unconfigured.
 * @param {{ feedUrl?: string|null, env?: NodeJS.ProcessEnv }} [opts]
 * @returns {string|null}
 */
function resolveFeedUrl(opts = {}) {
  if (opts.feedUrl != null && String(opts.feedUrl).trim() !== '') {
    return String(opts.feedUrl).trim();
  }
  const env = opts.env || process.env;
  const fromEnv = env[UPDATE_FEED_ENV];
  if (fromEnv == null || String(fromEnv).trim() === '') return null;
  return String(fromEnv).trim();
}

/**
 * Validate feed JSON shape and enforce channel echo (cross-channel reject).
 * @param {unknown} body
 * @param {'stable'|'beta'} requestedChannel
 * @returns {{ ok: true, channel: string, version?: string, notes?: string, url?: string }
 *   | { ok: false, code: string, message: string }}
 */
function validateFeedResponse(body, requestedChannel) {
  const want = normalizeChannel(requestedChannel);
  if (body == null || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, code: 'INVALID_SHAPE', message: 'Feed response must be a JSON object' };
  }
  const obj = /** @type {Record<string, unknown>} */ (body);
  if (typeof obj.channel !== 'string' || !obj.channel.trim()) {
    return { ok: false, code: 'MISSING_CHANNEL', message: 'Feed response missing channel echo' };
  }
  const echoed = normalizeChannel(obj.channel);
  // Reject if raw channel was unknown OR normalized echo ≠ request (cross-channel).
  const rawEcho = String(obj.channel).trim().toLowerCase();
  if (!CHANNELS.includes(rawEcho)) {
    return {
      ok: false,
      code: 'CHANNEL_MISMATCH',
      message: `Cross-channel reject: requested ${want}, feed echoed ${obj.channel}`,
    };
  }
  if (echoed !== want) {
    return {
      ok: false,
      code: 'CHANNEL_MISMATCH',
      message: `Cross-channel reject: requested ${want}, feed echoed ${echoed}`,
    };
  }
  const out = {
    ok: true,
    channel: echoed,
  };
  if (typeof obj.version === 'string') out.version = obj.version;
  if (typeof obj.notes === 'string') out.notes = obj.notes;
  if (typeof obj.url === 'string') out.url = obj.url;
  return out;
}

/**
 * Soft update check — never downloads or installs.
 * @param {{
 *   channel?: string,
 *   feedUrl?: string|null,
 *   env?: NodeJS.ProcessEnv,
 *   fetchImpl?: typeof fetch,
 *   currentVersion?: string,
 * }} [opts]
 * @returns {Promise<{
 *   status: 'unconfigured'|'ok'|'no_update'|'error',
 *   userMessage: string,
 *   channel?: string,
 *   feed?: object,
 *   code?: string,
 * }>}
 */
async function softCheckForUpdates(opts = {}) {
  const channel = normalizeChannel(opts.channel);
  const feedUrl = resolveFeedUrl(opts);
  if (!feedUrl) {
    return {
      status: 'unconfigured',
      userMessage: '업데이트 서버 미구성',
      channel,
      code: 'FEED_UNSET',
    };
  }

  const fetchImpl = opts.fetchImpl || globalThis.fetch;
  if (typeof fetchImpl !== 'function') {
    return {
      status: 'error',
      userMessage: '업데이트 확인을 사용할 수 없습니다 (fetch 없음)',
      channel,
      code: 'NO_FETCH',
    };
  }

  let url;
  try {
    url = new URL(feedUrl);
    url.searchParams.set('channel', channel);
    if (opts.currentVersion) url.searchParams.set('current', String(opts.currentVersion));
  } catch {
    return {
      status: 'error',
      userMessage: '업데이트 피드 URL이 올바르지 않습니다',
      channel,
      code: 'BAD_FEED_URL',
    };
  }

  let res;
  try {
    res = await fetchImpl(url.toString(), {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        'X-Ssak-Desktop-Channel': channel,
      },
    });
  } catch (err) {
    return {
      status: 'error',
      userMessage: '업데이트 서버에 연결하지 못했습니다',
      channel,
      code: 'FETCH_FAILED',
    };
  }

  if (!res || !res.ok) {
    const status = res && typeof res.status === 'number' ? res.status : '?';
    return {
      status: 'error',
      userMessage: `업데이트 서버 응답 오류 (${status})`,
      channel,
      code: 'HTTP_ERROR',
    };
  }

  let body;
  try {
    body = await res.json();
  } catch {
    return {
      status: 'error',
      userMessage: '업데이트 피드 JSON을 해석하지 못했습니다',
      channel,
      code: 'BAD_JSON',
    };
  }

  const validated = validateFeedResponse(body, channel);
  if (!validated.ok) {
    return {
      status: 'error',
      userMessage: validated.message,
      channel,
      code: validated.code,
    };
  }

  const current = opts.currentVersion != null ? String(opts.currentVersion) : null;
  if (validated.version && current && validated.version === current) {
    return {
      status: 'no_update',
      userMessage: `최신입니다 (${validated.channel} ${validated.version})`,
      channel: validated.channel,
      feed: validated,
    };
  }

  const ver = validated.version ? ` ${validated.version}` : '';
  return {
    status: 'ok',
    userMessage: `업데이트 정보 수신 (채널 ${validated.channel}${ver}) — 자동 설치 없음`,
    channel: validated.channel,
    feed: validated,
  };
}

module.exports = {
  CHANNELS,
  DEFAULT_CHANNEL,
  UPDATE_FEED_ENV,
  normalizeChannel,
  resolveFeedUrl,
  validateFeedResponse,
  softCheckForUpdates,
};
