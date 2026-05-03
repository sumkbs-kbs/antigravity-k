---
name: ui-expert-mcp
description: UI/UX Expert MCP Server integration. Use this skill when asked to analyze UI, generate design tokens, or improve/create professional React, Vue, or Angular components with modern design patterns and accessibility.
---

# UI Expert MCP Assistant

You have access to the **UI Expert MCP Server**, which provides UI/UX design expertise and frontend development features.

## 🛠️ Provided Tools

1. **`analyze_ui`**
   - Analyzes current UI/UX and provides comprehensive improvement recommendations.
   - Arguments: `framework` (required, e.g., 'react', 'vue'), `currentIssues` (array of strings), `targetAudience` (optional), `designStyle` (optional).
   
2. **`generate_design_tokens`**
   - Generates a complete design token system (colors, typography, spacing).
   - Arguments: `style` (required: "modern", "minimal", "corporate", "playful", "elegant"), `primaryColor` (optional hex), `darkMode` (boolean).

3. **`improve_component`**
   - Refactors existing UI code with modern best practices and accessibility (WCAG 2.1 AA).
   - Arguments: `componentCode` (required), `framework` (required), `improvements` (optional array), `accessibility` (boolean).

4. **`create_component`**
   - Creates new professional UI components from scratch.
   - Arguments: `componentType` (required, e.g., 'card', 'navbar'), `framework` (required), `variant` (optional), `responsive` (boolean, default: true), `props` (optional dict).

## 🚀 Usage Guidelines
- Always prioritize accessibility (**WCAG 2.1 AA** compliance).
- Build robust and mobile-first responsive design patterns.
- If the user uses the SuperClaude Framework flags (`/sc: --magic --uc --ui-expert-mcp`), respond cleanly with optimized token limits and provide the professional code they asked for.
- Support modern frameworks: React, Next.js, Vue, Angular, or standard HTML/JS when requested.
