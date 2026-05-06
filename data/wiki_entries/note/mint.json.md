---
id: 188
category: note
tags: []
created: 2026-05-04T09:42:52.617651
---

# mint.json

```json
{
  "$schema": "https://mintlify.com/schema.json",
  "name": "Claude Code Architecture",
  "logo": {
    "dark": "/docs/logo/dark.svg",
    "light": "/docs/logo/light.svg"
  },
  "favicon": "/docs/favicon.svg",
  "colors": {
    "primary": "#D97706",
    "light": "#F59E0B",
    "dark": "#B45309",
    "background": {
      "dark": "#0F172A",
      "light": "#FFFFFF"
    }
  },
  "metadata": {
    "og:image": "https://raw.githubusercontent.com/777genius/claude-code-working/main/docs/images/architecture-layers.png",
    "twitter:image": "https://raw.githubusercontent.com/777genius/claude-code-working/main/docs/images/architecture-layers.png",
    "twitter:card": "summary_large_image"
  },
  "topbarCtaButton": {
    "type": "github",
    "url": "https://github.com/777genius/claude-code-working"
  },
  "search": {
    "prompt": "Search Claude Code architecture documentation..."
  },
  "redirects": [
    {
      "source": "/docs/introduction",
      "destination": "/docs/introduction/what-is-claude-code"
    }
  ],
  "navigation": [
    {
      "group": "Start",
      "pages": [
        {
          "group": "Introduction",
          "pages": [
            "docs/introduction/what-is-claude-code",
            "docs/introduction/why-this-whitepaper",
            "docs/introduction/architecture-overview"
          ]
        }
      ]
    },
    {
      "group": "How the conversation works",
      "pages": [
        "docs/conversation/the-loop",
        "docs/conversation/streaming",
        "docs/conversation/multi-turn"
      ]
    },
    {
      "group": "Tools",
      "pages": [
        "docs/tools/what-are-tools",
        "docs/tools/file-operations",
        "docs/tools/shell-execution",
        "docs/tools/search-and-navigation",
        "docs/tools/task-management"
      ]
    },
    {
      "group": "Security and Permissions",
      "pages": [
        "docs/safety/why-safety-matters",
        "docs/safety/permission-model",
        "docs/safety/sandbox",
        "docs/safety/plan-mode"
      ]
    },
    {
      "group": "Project Context",
      "pages": [
        "docs/context/system-prompt",
        "docs/context/project-memory",
        "docs/context/compaction",
        "docs/context/token-budget"
      ]
    },
    {
      "group": "Multi-Agent Collaboration",
      "pages": [
        "docs/agent/sub-agents",
        "docs/agent/worktree-isolation",
        "docs/agent/coordinator-and-swarm"
      ]
    },
    {
      "group": "Extensibility",
      "pages": [
        "docs/extensibility/mcp-protocol",
        "docs/extensibility/hooks",
        "docs/extensibility/skills",
        "docs/extensibility/custom-agents"
      ]
    },
    {
      "group": "Internals and Hidden Features",
      "pages": [
        "docs/internals/three-tier-gating",
        "docs/internals/feature-flags",
        "docs/internals/growthbook-ab-testing",
        "docs/internals/hidden-features",
        "docs/internals/ant-only-world"
      ]
    }
  ],
  "footerSocials": {
    "github": "https://github.com/777genius/claude-code-working"
  }
}
```
