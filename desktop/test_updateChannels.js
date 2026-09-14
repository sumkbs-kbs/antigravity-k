/**
 * Tiny fixture test: channel echo + cross-channel reject + unconfigured soft-check.
 * Run: node desktop/test_updateChannels.js
 */
'use strict';

const assert = require('assert');
const path = require('path');
const fs = require('fs');
const {
  UPDATE_FEED_ENV,
  normalizeChannel,
  resolveFeedUrl,
  validateFeedResponse,
  softCheckForUpdates,
} = require('./updateChannels');

const fixturesDir = path.join(__dirname, 'fixtures');
const stableBody = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, 'update_feed_stable.json'), 'utf8'),
);
const betaBody = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, 'update_feed_beta.json'), 'utf8'),
);

assert.strictEqual(normalizeChannel('BETA'), 'beta');
assert.strictEqual(normalizeChannel('nope'), 'stable');
assert.strictEqual(UPDATE_FEED_ENV, 'SSAK_UPDATE_FEED');

assert.strictEqual(resolveFeedUrl({ env: {} }), null);
assert.strictEqual(resolveFeedUrl({ env: { SSAK_UPDATE_FEED: '  ' } }), null);
assert.strictEqual(
  resolveFeedUrl({ env: { SSAK_UPDATE_FEED: 'https://example.test/feed.json' } }),
  'https://example.test/feed.json',
);

const ok = validateFeedResponse(stableBody, 'stable');
assert.strictEqual(ok.ok, true);
assert.strictEqual(ok.channel, 'stable');
assert.strictEqual(ok.version, '0.1.1');

const mismatch = validateFeedResponse(betaBody, 'stable');
assert.strictEqual(mismatch.ok, false);
assert.strictEqual(mismatch.code, 'CHANNEL_MISMATCH');

const badShape = validateFeedResponse(null, 'stable');
assert.strictEqual(badShape.ok, false);

(async () => {
  const unset = await softCheckForUpdates({ env: {}, channel: 'stable' });
  assert.strictEqual(unset.status, 'unconfigured');
  assert.strictEqual(unset.userMessage, '업데이트 서버 미구성');

  const fetchOk = async () => ({
    ok: true,
    status: 200,
    json: async () => stableBody,
  });
  const checked = await softCheckForUpdates({
    channel: 'stable',
    feedUrl: 'https://example.test/feed.json',
    currentVersion: '0.1.0',
    fetchImpl: fetchOk,
  });
  assert.strictEqual(checked.status, 'ok');
  assert.strictEqual(checked.channel, 'stable');
  assert.match(checked.userMessage, /자동 설치 없음/);

  const fetchMismatch = async () => ({
    ok: true,
    status: 200,
    json: async () => betaBody,
  });
  const rejected = await softCheckForUpdates({
    channel: 'stable',
    feedUrl: 'https://example.test/feed.json',
    fetchImpl: fetchMismatch,
  });
  assert.strictEqual(rejected.status, 'error');
  assert.strictEqual(rejected.code, 'CHANNEL_MISMATCH');

  console.log('test_updateChannels: OK');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
