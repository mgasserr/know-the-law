# Frontend File Structure & Directory Listing

## Complete Directory Tree

```
d:\Final AI Project WE\frontend\
│
├── src/
│   ├── components/
│   │   ├── Header.tsx                     # Top navigation bar
│   │   ├── Header.module.css              # Header styles
│   │   ├── BotSelector.tsx                # Bot selection tabs
│   │   ├── BotSelector.module.css         # Bot selector styles
│   │   ├── ChatWindow.tsx                 # Message display area
│   │   ├── ChatWindow.module.css          # Chat window styles
│   │   ├── Message.tsx                    # Individual message
│   │   ├── Message.module.css             # Message styles
│   │   ├── Citation.tsx                   # Citation/reference
│   │   ├── Citation.module.css            # Citation styles
│   │   ├── InputArea.tsx                  # Text input area
│   │   ├── InputArea.module.css           # Input area styles
│   │   ├── VoiceInput.tsx                 # Microphone recording
│   │   └── VoiceInput.module.css          # Voice input styles
│   │
│   ├── services/
│   │   └── chatbotAPI.ts                  # API client (Axios)
│   │
│   ├── store/
│   │   └── conversationStore.ts           # State management (Zustand)
│   │
│   ├── styles/
│   │   └── global.css                     # Global styles & variables
│   │
│   ├── utils/
│   │   ├── audioRecorder.ts               # Audio recording utility
│   │   └── helpers.ts                     # Helper functions
│   │
│   ├── App.tsx                            # Main application component
│   ├── App.module.css                     # Main app styles
│   └── main.tsx                           # React entry point
│
├── public/                                 # Static assets (if needed)
│
├── index.html                              # HTML template
│
├── vite.config.ts                          # Vite build configuration
├── tsconfig.json                           # TypeScript configuration
│
├── package.json                            # Dependencies & scripts
├── .env.example                            # Environment template
├── .gitignore                              # Git ignore rules
│
└── Documentation/
    ├── README.md                           # Main documentation
    ├── PROJECT_SUMMARY.md                  # Project overview
    ├── DEVELOPMENT.md                      # Development guide
    ├── DEPLOYMENT.md                       # Deployment instructions
    ├── API_INTEGRATION.md                  # API documentation
    ├── ARCHITECTURE.md                     # System architecture
    ├── TESTING.md                          # Testing strategy
    └── COMPLETION_CHECKLIST.md             # Project checklist

```

## File Count by Type

```
TypeScript Files:
  - Components: 7 (.tsx files)
  - Services: 1
  - Store: 1
  - Utils: 2
  Total: 11 files

CSS/Styling:
  - Global: 1
  - Component Modules: 7
  - Total: 8 files

Configuration:
  - vite.config.ts
  - tsconfig.json
  - package.json
  - .env.example
  - .gitignore
  - index.html
  Total: 6 files

Documentation:
  - README.md
  - PROJECT_SUMMARY.md
  - DEVELOPMENT.md
  - DEPLOYMENT.md
  - API_INTEGRATION.md
  - ARCHITECTURE.md
  - TESTING.md
  - COMPLETION_CHECKLIST.md
  Total: 8 files

GRAND TOTAL: ~33 files
```

## File Sizes (Approximate)

| File | Type | Size |
|------|------|------|
| src/components/Header.tsx | TS | ~2 KB |
| src/components/BotSelector.tsx | TS | ~1.5 KB |
| src/components/ChatWindow.tsx | TS | ~3 KB |
| src/components/Message.tsx | TS | ~2 KB |
| src/components/Citation.tsx | TS | ~2 KB |
| src/components/InputArea.tsx | TS | ~2.5 KB |
| src/components/VoiceInput.tsx | TS | ~3.5 KB |
| src/services/chatbotAPI.ts | TS | ~4 KB |
| src/store/conversationStore.ts | TS | ~2 KB |
| src/utils/audioRecorder.ts | TS | ~2.5 KB |
| src/utils/helpers.ts | TS | ~3 KB |
| src/App.tsx | TS | ~2.5 KB |
| src/main.tsx | TS | ~0.5 KB |
| src/styles/global.css | CSS | ~8 KB |
| Component CSS Modules | CSS | ~12 KB (total) |
| index.html | HTML | ~3 KB |
| package.json | JSON | ~1 KB |
| vite.config.ts | TS | ~1 KB |
| tsconfig.json | JSON | ~0.5 KB |
| Documentation | MD | ~60 KB (total) |
| **Total** | | **~139 KB** |

## Dependencies Summary

### Production Dependencies
```
react:                 ^18.2.0
react-dom:             ^18.2.0
react-icons:           ^5.0.1
axios:                 ^1.6.0
react-markdown:        ^9.0.1
date-fns:              ^2.30.0
zustand:               ^4.4.1
classnames:            ^2.3.2
```

### Development Dependencies
```
@types/react:          ^18.2.0
@types/react-dom:      ^18.2.0
@types/node:           ^20.0.0
@vitejs/plugin-react:  ^4.0.0
typescript:            ^5.0.0
vite:                  ^4.3.0
```

## Component Hierarchy Map

```
App
│
├─ Header
│  ├─ Status Indicator
│  └─ Action Buttons (Clear, Info)
│
├─ BotSelector
│  ├─ Bot Tab 1 (مستشار القوانين)
│  └─ Bot Tab 2 (محلل الأحكام)
│
├─ ChatWindow
│  ├─ Empty State (when no messages)
│  │  └─ Suggestion Boxes
│  │
│  ├─ Error Banner (if error exists)
│  │
│  ├─ Messages Container
│  │  └─ Message (repeated)
│  │     ├─ Message Bubble
│  │     │  ├─ Message Text
│  │     │  ├─ Citations Container (if citations)
│  │     │  │  └─ Citation (repeated)
│  │     │  │     ├─ Citation Chip (clickable)
│  │     │  │     └─ Expanded Content (conditional)
│  │     │  │
│  │     │  └─ Message Footer (timestamp)
│  │
│  └─ Loading Indicator (if loading)
│     └─ Loading Dots Animation
│
└─ InputArea
   ├─ VoiceInput
   │  ├─ Mic Button
   │  ├─ Stop Button (recording state)
   │  ├─ Cancel Button (recording state)
   │  ├─ Recording Indicator
   │  └─ Error Message
   │
   ├─ Textarea
   │  └─ Auto-resizing input field
   │
   └─ Send Button
      └─ Send Icon (MdSend)
```

## State Flow Diagram

```
conversationStore (Global State)
│
├─ currentBot: 'bot1' | 'bot2'
│  │
│  ├─ Used by: BotSelector, App, ChatbotAPI
│  └─ Updated by: setCurrentBot()
│
├─ messages: Message[]
│  │
│  ├─ Used by: ChatWindow, Message, InputArea
│  └─ Updated by: addMessage(), setMessages(), clearConversation()
│
├─ isLoading: boolean
│  │
│  ├─ Used by: ChatWindow (loading indicator), InputArea (button disable)
│  └─ Updated by: setLoading()
│
└─ error: string | null
   │
   ├─ Used by: ChatWindow (error banner), App
   └─ Updated by: setError(), clearConversation()
```

## API Call Points

```
API Calls Made From:

1. App.tsx
   └─ chatbotAPI.healthCheck() → Backend /health
   └─ chatbotAPI.chatBot1/2() → Backend /chat

2. InputArea.tsx
   └─ VoiceInput calls chatbotAPI.transcribeAudio() → Backend /transcribe

3. (Future) ChatWindow.tsx
   └─ Could call chatbotAPI.getConversationHistory() → Backend /history/{id}
   └─ Could call chatbotAPI.clearHistory() → Backend /history/{id}
```

## Environment Variables Used

```
REACT_APP_API_URL
├─ Used in: src/services/chatbotAPI.ts
├─ Default: http://localhost:8000
└─ Purpose: Backend server URL

REACT_APP_BOT1_NAME
├─ Used in: src/utils/helpers.ts
├─ Default: مستشار القوانين
└─ Purpose: Display name for Bot 1

REACT_APP_BOT2_NAME
├─ Used in: src/utils/helpers.ts
├─ Default: محلل الأحكام
└─ Purpose: Display name for Bot 2

REACT_APP_ENABLE_VOICE
├─ Used in: Can be checked in components
├─ Default: true
└─ Purpose: Enable/disable voice features

REACT_APP_ENABLE_TTS
├─ Used in: Can be checked in components
├─ Default: false
└─ Purpose: Enable/disable text-to-speech
```

## CSS Variable System

### Color Palette
```
Primary:
  --primary: #1e3a8a
  --primary-light: #3b82f6
  --primary-dark: #1e40af

Secondary:
  --secondary: #7c3aed
  --secondary-light: #a78bfa

Status Colors:
  --success: #10b981
  --warning: #f59e0b
  --error: #ef4444

Neutrals (9 levels):
  --neutral-50 to --neutral-900
```

### Spacing Scale
```
--spacing-xs: 0.25rem   (4px)
--spacing-sm: 0.5rem    (8px)
--spacing-md: 1rem      (16px)
--spacing-lg: 1.5rem    (24px)
--spacing-xl: 2rem      (32px)
--spacing-2xl: 3rem     (48px)
```

### Border Radius
```
--radius-sm: 0.375rem   (6px)
--radius-md: 0.5rem     (8px)
--radius-lg: 0.75rem    (12px)
--radius-xl: 1rem       (16px)
```

### Shadows
```
--shadow-sm:  Small drop shadow
--shadow-md:  Medium drop shadow
--shadow-lg:  Large drop shadow
--shadow-xl:  Extra large drop shadow
```

## Build Output Structure

After running `npm run build`:

```
frontend/dist/
│
├── index.html              # Entry HTML (modified by build)
│
├── assets/
│   ├── index-xxxxx.js      # Main JavaScript bundle
│   ├── vendor-xxxxx.js     # Vendor bundle (React, etc.)
│   ├── app-xxxxx.css       # All CSS concatenated & minified
│   └── ...                 # Other assets
│
└── (Optional)
    └── _redirects          # For Vercel/Netlify routing
```

## Development vs Production

### Development (`npm run dev`)
- Source maps enabled
- Hot module replacement (HMR)
- Unminified code
- Full error messages
- Slow build time

### Production (`npm run build`)
- Source maps disabled
- Code minification
- Tree shaking
- Asset optimization
- Fast load time

## Responsive Breakpoints

```
Desktop:     1024px and up
Tablet:      768px to 1023px
Mobile:      Below 768px
```

Each component uses media queries at these breakpoints for responsive adjustments.

---

**Total Code**: ~3,500+ lines of TypeScript/CSS
**Documentation**: ~8,000+ lines of Markdown
**Project Status**: ✅ Complete and Ready
**Last Updated**: September 2026
