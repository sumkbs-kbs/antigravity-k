"use strict";

const bundled = require("../korean-character-count/scripts/korean_character_count.js");

if (require.main === module) {
  try {
    bundled.main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

module.exports = bundled;
