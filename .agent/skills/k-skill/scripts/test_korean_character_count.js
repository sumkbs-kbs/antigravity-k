const test = require("node:test");
const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  countLines,
  countNeisBytes,
  countUtf8Bytes,
  createReport,
  parseArgs,
} = require("./korean_character_count.js");

test("createReport counts graphemes, lines, and bytes with the default contract", () => {
  const sample = "한🙂\r\n둘째 줄";
  const report = createReport(sample);

  assert.equal(report.profile, "default");
  assert.equal(report.counts.characters, 7);
  assert.equal(report.counts.characters_without_whitespace, 5);
  assert.equal(report.counts.lines, 2);
  assert.equal(report.counts.bytes, countUtf8Bytes(sample));
  assert.equal(report.counts.bytes_utf8, report.counts.bytes);
  assert.equal(report.counts.bytes_neis, countNeisBytes(sample));
  assert.match(report.contract.characters, /grapheme/i);
  assert.match(report.contract.bytes, /UTF-8/);
});

test("countLines treats CRLF, CR, LF, and Unicode separators as one line break each", () => {
  assert.equal(countLines(""), 0);
  assert.equal(countLines("가"), 1);
  assert.equal(countLines("가\n"), 2);
  assert.equal(countLines("가\r\n나\r다\u2028라\u2029마"), 5);
});

test("countNeisBytes applies Hangul 3-byte, ASCII 1-byte, and newline 2-byte rules", () => {
  assert.equal(countNeisBytes("가A 1\n나🙂"), 15);
  assert.equal(countNeisBytes("ABC"), 3);
  assert.equal(countNeisBytes("한글"), 6);
});

test("countNeisBytes falls back to UTF-8 bytes for non-Hangul graphemes", () => {
  assert.equal(countUtf8Bytes("\u0301"), 2);
  assert.equal(countNeisBytes("\u0301"), 2);
  assert.equal(countNeisBytes("🙂"), countUtf8Bytes("🙂"));
});

test("parseArgs enforces one input source and validates the profile", () => {
  assert.deepEqual(parseArgs(["--text", "가나다"]), {
    format: "json",
    inputMode: "text",
    profile: "default",
    text: "가나다",
  });

  assert.throws(() => parseArgs(["--text", "가", "--file", "sample.txt"]), /exactly one input source/i);
  assert.throws(() => parseArgs(["--text", "가", "--text", "나"]), /exactly one input source/i);
  assert.throws(() => parseArgs(["--profile", "legacy", "--text", "가"]), /unknown profile/i);
});

test("CLI accepts text, file, and stdin input", () => {
  const repoRoot = path.join(__dirname, "..");
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "korean-character-count-cli-"));
  const samplePath = path.join(tempDir, "sample.txt");

  try {
    fs.writeFileSync(samplePath, "가나다\nABC", "utf8");

    const textOutput = JSON.parse(
      childProcess.execFileSync("node", ["scripts/korean_character_count.js", "--text", "가나다", "--format", "json"], {
        cwd: repoRoot,
        encoding: "utf8",
      }),
    );
    assert.equal(textOutput.counts.characters, 3);
    assert.equal(textOutput.counts.bytes_utf8, 9);

    const fileOutput = JSON.parse(
      childProcess.execFileSync("node", ["scripts/korean_character_count.js", "--file", samplePath, "--format", "json"], {
        cwd: repoRoot,
        encoding: "utf8",
      }),
    );
    assert.equal(fileOutput.counts.lines, 2);
    assert.equal(fileOutput.counts.bytes_utf8, countUtf8Bytes("가나다\nABC"));

    const stdinOutput = JSON.parse(
      childProcess.execFileSync("node", ["scripts/korean_character_count.js", "--stdin", "--profile", "neis"], {
        cwd: repoRoot,
        encoding: "utf8",
        input: "가나다\nABC",
      }),
    );
    assert.equal(stdinOutput.profile, "neis");
    assert.equal(stdinOutput.counts.bytes, countNeisBytes("가나다\nABC"));

    const duplicateText = childProcess.spawnSync(
      "node",
      ["scripts/korean_character_count.js", "--text", "가나다", "--text", "라마바", "--format", "json"],
      {
        cwd: repoRoot,
        encoding: "utf8",
      },
    );
    assert.notEqual(duplicateText.status, 0);
    assert.match(duplicateText.stderr, /exactly one input source/i);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});
