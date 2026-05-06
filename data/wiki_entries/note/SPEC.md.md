---
id: 198
category: note
tags: []
created: 2026-05-04T09:42:52.665205
---

# SPEC.md

```markdown
# Implementation Plan - NanoBanana PRO Obsidian Plugin

## Goal Description
Convert the existing `nanoBananaInfographic.js` QuickAdd script into a full-featured Obsidian Community Plugin named `nanobanana-pro-obsidian`.
The plugin will generate "Knowledge Posters" (infographics) from Obsidian notes using AI.

## Core Features

### Three-Step Process
1. **Prompt Generation**: Analyze the note content and generate a detailed image prompt
   - Configurable providers: OpenAI, Gemini, Anthropic, XAI
2. **Image Generation**: Generate the infographic using Google's Gemini model
   - Default: `gemini-2.0-flash-exp` (with image generation capability)
3. **Embed**: Save the image locally and embed it at the top of the note

## Plugin Structure

```
nanobanana-pro-obsidian/
├── manifest.json           # Plugin metadata
├── package.json            # NPM configuration
├── tsconfig.json           # TypeScript configuration
├── esbuild.config.mjs      # Build configuration
├── README.md               # Documentation
├── SPEC.md                 # This file
├── styles.css              # Plugin styles
└── src/
    ├── main.ts             # Main plugin class
    ├── types.ts            # Type definitions
    ├── settings.ts         # Settings tab UI
    ├── settingsData.ts     # Default settings
    ├── progressModal.ts    # Progress modal UI
    ├── previewModal.ts     # Prompt preview modal
    └── services/
        ├── promptService.ts    # AI prompt generation
        ├── imageService.ts     # Image generation
        └── fileService.ts      # File operations
```

## Settings Configuration

### API Keys Section
| Setting | Type | Description |
|---------|------|-------------|
| `googleApiKey` | string | Google AI API key (for image generation) |
| `openaiApiKey` | string | OpenAI API key |
| `anthropicApiKey` | string | Anthropic API key |
| `xaiApiKey` | string | xAI API key |

### Prompt Generation Section
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `selectedProvider` | enum | 'google' | AI provider for prompt generation |
| `promptModel` | string | 'gemini-2.0-flash-exp' | Model name for prompt generation |

### Image Generation Section
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `imageModel` | string | 'gemini-2.0-flash-exp' | Model for image generation |
| `imageStyle` | enum | 'infographic' | Style preset |

### UX Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `showPreviewBeforeGeneration` | boolean | true | Show prompt preview before generating |
| `attachmentFolder` | string | '999-Attachments' | Folder to save images |
| `autoRetryCount` | number | 2 | Auto-retry on failure |
| `showProgressModal` | boolean | true | Show progress during generation |

## UX Enhancement Features

### 1. Progress Modal
Real-time feedback during the generation process:

```
┌─────────────────────────────────────────┐
│  🎨 Knowledge Poster 생성 중...          │
│                                         │
│  ████████████░░░░░░░░ 60%              │
│                                         │
│  ✅ 1. 노트 분석 완료                    │
│  ✅ 2. 프롬프트 생성 완료                 │
│  🔄 3. 이미지 생성 중...                 │
│  ⏳ 4. 파일 저장 대기                    │
│                                         │
│  예상 소요 시간: 약 15-30초              │
│                                         │
│  [취소]                                 │
└─────────────────────────────────────────┘
```

### 2. Prompt Preview Modal
Optional preview and edit before image generation:

```
┌─────────────────────────────────────────┐
│  📝 프롬프트 미리보기                     │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │ Create a visually stunning     │   │
│  │ infographic poster about...    │   │
│  │ [editable text area]           │   │
│  └─────────────────────────────────┘   │
│                                         │
│  🤖 모델: gemini-2.0-flash-exp          │
│  📊 스타일: Infographic                  │
│                                         │
│  [이미지 생성] [다시 생성] [취소]          │
└─────────────────────────────────────────┘
```

### 3. Error Handling System

#### Error Types & User Messages
| Error Type | User Message | Action |
|------------|--------------|--------|
| `INVALID_API_KEY` | "API 키가 유효하지 않습니다. 설정을 확인해주세요." | Open settings |
| `RATE_LIMIT` | "API 요청 한도 초과. 잠시 후 다시 시도해주세요." | Auto-retry |
| `NETWORK_ERROR` | "네트워크 연결 오류. 인터넷 연결을 확인해주세요." | Retry button |
| `GENERATION_FAILED` | "이미지 생성 실패. 다른 스타일로 시도해보세요." | Suggest alternatives |
| `CONTENT_FILTERED` | "콘텐츠 정책으로 인해 생성할 수 없습니다." | Modify prompt |

#### Auto-Retry Logic
```typescript
async function executeWithRetry<T>(
  operation: () => Promise<T>,
  maxRetries: number = 2,
  delay: number = 1000
): Promise<T> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      if (attempt === maxRetries) throw error;
      if (!isRetryableError(error)) throw error;
      await sleep(delay * Math.pow(2, attempt)); // Exponential backoff
    }
  }
}
```

### 4. Success Notification
```
┌─────────────────────────────────────┐
│ ✅ Knowledge Poster 생성 완료!       │
│                                     │
│ 📁 저장 위치: 999-Attachments/      │
│ 📄 파일명: note-poster-2025.png     │
│                                     │
│ [노트 보기] [갤러리 열기]            │
└─────────────────────────────────────┘
```

## Commands

| Command | Description |
|---------|-------------|
| `Generate Knowledge Poster` | Full generation process |
| `Generate Prompt Only` | Generate and copy prompt to clipboard |
| `Regenerate Last Poster` | Retry last generation |
| `Open Settings` | Open plugin settings |

## API Integration

### Prompt Generation Endpoints
| Provider | Endpoint | Auth Header |
|----------|----------|-------------|
| OpenAI | `https://api.openai.com/v1/chat/completions` | `Authorization: Bearer {key}` |
| Google | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | `x-goog-api-key: {key}` |
| Anthropic | `https://api.anthropic.com/v1/messages` | `x-api-key: {key}` |
| xAI | `https://api.x.ai/v1/chat/completions` | `Authorization: Bearer {key}` |

### Image Generation
Google Gemini with image output:
```typescript
const response = await fetch(
  `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-goog-api-key': apiKey
    },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        responseModalities: ["TEXT", "IMAGE"]
      }
    })
  }
);
```

## File Operations

### Image Saving
1. Parse base64 image from API response
2. Generate unique filename: `{noteBasename}-poster-{timestamp}.png`
3. Save to configured attachment folder
4. Return relative path for embedding

### Note Modification
1. Read current note content
2. Check for existing poster embed
3. Insert/replace image embed at top of note
4. Preserve frontmatter if exists

## Verification Plan

### Build Verification
```bash
npm install
npm run build
# Should produce main.js without errors
```

### Manual Testing Checklist
- [ ] Plugin loads in Obsidian without errors
- [ ] Settings tab displays all options correctly
- [ ] API key validation works for each provider
- [ ] Progress modal shows during generation
- [ ] Prompt preview modal works correctly
- [ ] Image saves to correct folder
- [ ] Image embeds at top of note
- [ ] Error messages display appropriately
- [ ] Auto-retry works on transient failures
- [ ] Cancel button stops generation

## Distribution

### GitHub Repository Structure
```
nanobanana-pro-obsidian/
├── .github/
│   └── workflows/
│       └── release.yml     # Auto-release workflow
├── src/                    # Source files
├── manifest.json
├── package.json
├── README.md
└── ...
```

### BRAT Installation
Users can install via BRAT by adding:
```
username/nanobanana-pro-obsidian
```

### Release Files
- `main.js` - Compiled plugin
- `manifest.json` - Plugin metadata
- `styles.css` - Plugin styles

## Version History

| Version | Changes |
|---------|---------|
| 1.0.0 | Initial release with core features |

---

> **Note**: Model names like `gemini-2.0-flash-exp` may change. The plugin allows manual model name input for future compatibility.
```
