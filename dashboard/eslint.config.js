import js from "@eslint/js";

const browserGlobals = {
  alert: "readonly",
  AbortController: "readonly",
  atob: "readonly",
  Blob: "readonly",
  btoa: "readonly",
  clearInterval: "readonly",
  clearTimeout: "readonly",
  confirm: "readonly",
  console: "readonly",
  CustomEvent: "readonly",
  Diff2HtmlUI: "readonly",
  document: "readonly",
  Event: "readonly",
  EventSource: "readonly",
  fetch: "readonly",
  FileReader: "readonly",
  FitAddon: "readonly",
  FormData: "readonly",
  history: "readonly",
  Headers: "readonly",
  localStorage: "readonly",
  location: "readonly",
  MarkdownIt: "readonly",
  Matter: "readonly",
  monaco: "readonly",
  navigator: "readonly",
  prompt: "readonly",
  requestAnimationFrame: "readonly",
  require: "readonly",
  setInterval: "readonly",
  setTimeout: "readonly",
  Split: "readonly",
  Terminal: "readonly",
  TextDecoder: "readonly",
  URL: "readonly",
  WebSocket: "readonly",
  window: "readonly",
};

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  js.configs.recommended,
  {
    files: ["src/**/*.js", "*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: browserGlobals,
    },
    rules: {
      "no-empty": ["error", { allowEmptyCatch: true }],
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["vite.config.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        console: "readonly",
        process: "readonly",
      },
    },
  },
];
