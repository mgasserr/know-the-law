# Frontend Architecture & System Design

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │              React Application                   │   │
│  ├──────────────────────────────────────────────────┤   │
│  │                                                  │   │
│  │  ┌────────────────────────────────────────────┐ │   │
│  │  │         UI Layer (Components)             │ │   │
│  │  ├────────────────────────────────────────────┤ │   │
│  │  │ • Header                                  │ │   │
│  │  │ • BotSelector                            │ │   │
│  │  │ • ChatWindow                             │ │   │
│  │  │ • Message                                │ │   │
│  │  │ • Citation                               │ │   │
│  │  │ • InputArea                              │ │   │
│  │  │ • VoiceInput                             │ │   │
│  │  └────────────────────────────────────────────┘ │   │
│  │                      ↑                          │   │
│  │                      ↓                          │   │
│  │  ┌────────────────────────────────────────────┐ │   │
│  │  │    State Management (Zustand)             │ │   │
│  │  ├────────────────────────────────────────────┤ │   │
│  │  │ • conversationStore                       │ │   │
│  │  │   - currentBot                            │ │   │
│  │  │   - messages[]                            │ │   │
│  │  │   - isLoading                             │ │   │
│  │  │   - error                                 │ │   │
│  │  └────────────────────────────────────────────┘ │   │
│  │                      ↑                          │   │
│  │                      ↓                          │   │
│  │  ┌────────────────────────────────────────────┐ │   │
│  │  │      Service Layer (API & Utilities)      │ │   │
│  │  ├────────────────────────────────────────────┤ │   │
│  │  │ • chatbotAPI (Axios)                      │ │   │
│  │  │ • audioRecorder                           │ │   │
│  │  │ • helpers & utils                         │ │   │
│  │  └────────────────────────────────────────────┘ │   │
│  │                                                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
└─────────────────────────────────────────────────────────┘
                            ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────┐
│                   Backend Server                        │
│              (FastAPI on port 8000)                     │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  POST   /chat              - Chat endpoint              │
│  POST   /transcribe        - Audio transcription        │
│  GET    /history/{id}      - Get conversation history   │
│  DELETE /history/{id}      - Clear history              │
│  POST   /tts               - Text-to-speech             │
│  GET    /health            - Health check               │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## Component Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         App                                  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Header (Displays title, status, clear button)         │  │
│  └────────────────────────────────────────────────────────┘  │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ BotSelector (Switch between Bot1 and Bot2)            │  │
│  └────────────────────────────────────────────────────────┘  │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ChatWindow (Displays messages)                         │  │
│  │ ┌──────────────────────────────────────────────────┐  │  │
│  │ │ Message #1 (User)                               │  │  │
│  │ └──────────────────────────────────────────────────┘  │  │
│  │ ┌──────────────────────────────────────────────────┐  │  │
│  │ │ Message #2 (Bot)                                │  │  │
│  │ │ ┌──────────────────────────────────────────────┐│  │  │
│  │ │ │ Citation #1 (Statute)      | Citation #2   ││  │  │
│  │ │ └──────────────────────────────────────────────┘│  │  │
│  │ └──────────────────────────────────────────────────┘  │  │
│  │ ... more messages ...                                 │  │
│  └────────────────────────────────────────────────────────┘  │
│                          ↓                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ InputArea (Text + Voice Input)                        │  │
│  │ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │  │
│  │ │ VoiceInput   │  │ Textarea     │  │ Send Button  │ │  │
│  │ │ (Mic icon)   │  │ (Input text) │  │              │ │  │
│  │ └──────────────┘  └──────────────┘  └──────────────┘ │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
User Types/Speaks
    ↓
    ├─→ Text Input (InputArea)
    │       ↓
    │   Store in state
    │
    └─→ Voice Input (VoiceInput)
            ↓
        AudioRecorder.start()
            ↓
        User Records Audio
            ↓
        AudioRecorder.stop() → Blob
            ↓
        chatbotAPI.transcribeAudio(blob)
            ↓
        Backend: Whisper
            ↓
        Return: transcribed text
            ↓
        Add to textarea
            ↓
            
User clicks Send
    ↓
InputArea validates message
    ↓
chatbotAPI.sendMessage()
    ↓
Add to Store (user message)
    ↓
Set Loading = true
    ↓
Backend: /chat endpoint
    ↓
Backend processes with RAG + LLM
    ↓
Return: {content, citations[], timestamp}
    ↓
Add to Store (bot message)
    ↓
Set Loading = false
    ↓
ChatWindow displays new message
    ↓
Message renders with Citations
    ↓
Auto-scroll to bottom
```

## State Management Flow

```
ConversationStore (Zustand)
│
├─ currentBot: 'bot1' | 'bot2'
│  └─ Used to determine which bot to send messages to
│
├─ messages: Message[]
│  ├─ id: string
│  ├─ role: 'user' | 'assistant'
│  ├─ content: string
│  ├─ bot: 'bot1' | 'bot2'
│  ├─ timestamp: number
│  └─ citations?: Citation[]
│
├─ isLoading: boolean
│  └─ Used to disable input and show loading indicator
│
├─ error: string | null
│  └─ Display error messages to user
│
└─ Actions:
   ├─ setCurrentBot(bot) → switch active bot
   ├─ addMessage(message) → add to messages array
   ├─ setLoading(loading) → update loading state
   ├─ setError(error) → update error state
   ├─ clearConversation() → reset all
   └─ setMessages(messages) → replace messages array
```

## Message Types & Flow

### User Message
```typescript
{
  id: "msg-1",
  role: "user",
  content: "ما هي المادة 50؟",
  bot: "bot1",
  timestamp: 1693123456789
}
```

### Bot Message with Citations
```typescript
{
  id: "msg-2",
  role: "assistant",
  content: "المادة 50 من قانون المرافعات تنص على...",
  bot: "bot1",
  timestamp: 1693123457000,
  citations: [
    {
      id: "cite-1",
      text: "المادة 50",
      source: "المادة 50 - قانون المرافعات",
      type: "statute",
      fullText: "... النص الكامل ..."
    }
  ]
}
```

## API Integration Points

```
Frontend Components
        ↓
    InputArea
        ↓
    chatbotAPI Service
    ├── sendMessage()
    ├── transcribeAudio()
    ├── getConversationHistory()
    ├── clearHistory()
    ├── synthesizeSpeech()
    └── healthCheck()
        ↓
    Axios HTTP Client
        ↓
    Backend Endpoints
    ├── POST /chat
    ├── POST /transcribe
    ├── GET  /history/{id}
    ├── DELETE /history/{id}
    ├── POST /tts
    ├── GET  /health
    └── GET  /bot/{id}/info
```

## Styling Architecture

```
Styling System
│
├─ Global CSS (src/styles/global.css)
│  ├─ CSS Variables
│  │  ├─ Colors (primary, secondary, error, success, etc.)
│  │  ├─ Spacing (xs, sm, md, lg, xl, 2xl)
│  │  ├─ Border Radius (sm, md, lg, xl, full)
│  │  ├─ Shadows (sm, md, lg, xl)
│  │  └─ Transitions (fast, normal, slow)
│  │
│  ├─ Base Styles
│  │  ├─ Body
│  │  ├─ Typography (h1-h6, p, a)
│  │  ├─ Forms (input, textarea, select)
│  │  └─ Buttons
│  │
│  └─ Utility Classes
│     ├─ Text (text-center, text-primary, etc.)
│     ├─ Flexbox (flex, flex-col, flex-center, etc.)
│     ├─ Spacing (p-md, m-lg, gap-xl, etc.)
│     ├─ Sizing (rounded-lg, shadow-md, etc.)
│     └─ Visibility (hidden, invisible)
│
└─ Component CSS Modules (*.module.css)
   ├─ Header.module.css
   ├─ BotSelector.module.css
   ├─ ChatWindow.module.css
   ├─ Message.module.css
   ├─ Citation.module.css
   ├─ InputArea.module.css
   └─ VoiceInput.module.css
```

## Responsive Design Breakpoints

```
Desktop (1024px+)
├─ Full sidebar
├─ Multiple columns
└─ All features visible

Tablet (768px - 1023px)
├─ Adjusted spacing
├─ Optimized layouts
└─ Touch-friendly buttons

Mobile (< 768px)
├─ Single column
├─ Vertical stacking
├─ Large touch targets
└─ Simplified navigation
```

## Voice Recording Flow

```
User clicks Mic Button
    ↓
Request Microphone Permission
    ├─ Granted → AudioRecorder.startRecording()
    │   ├─ Get MediaStream
    │   ├─ Create MediaRecorder
    │   ├─ Start recording
    │   └─ Show recording indicator
    │
    └─ Denied → Show error message

Recording in Progress
    ├─ User can stop (Stop Button)
    └─ User can cancel (Cancel Button)

User clicks Stop Button
    ↓
AudioRecorder.stopRecording()
    ├─ Stop recording
    ├─ Collect audio chunks
    └─ Create Blob
        ↓
    Send to chatbotAPI.transcribeAudio(blob)
        ↓
    Backend: Whisper
        ├─ Decode audio
        ├─ Convert to text
        └─ Return transcript
            ↓
        Display in textarea
            ↓
        User can edit and send
```

## Error Handling Flow

```
API Call
    ↓
    ├─ Success (200)
    │  └─ Process response
    │     └─ Update store
    │
    ├─ Client Error (4xx)
    │  ├─ Validation Error → Show validation message
    │  ├─ Not Found (404) → Show "not found" message
    │  └─ Other → Show error banner
    │
    ├─ Server Error (5xx)
    │  └─ Show "server error" message
    │
    └─ Network Error
       ├─ Try again prompt
       └─ Show offline indicator

Error Display
    ├─ Error Banner (top of chat)
    ├─ Console Log (development)
    └─ User-friendly Message
```

## Performance Optimization Strategies

```
Code Splitting
├─ Components loaded on demand
├─ Lazy loading for routes
└─ Tree shaking unused code

Caching
├─ HTTP cache headers
├─ Browser cache
└─ Local storage (optional)

Optimization
├─ Minification (Vite)
├─ Gzip compression
├─ Image optimization
└─ CSS module bundling

Monitoring
├─ Performance metrics
├─ Error tracking
└─ User analytics
```

## Security Architecture

```
Frontend Security
├─ Input Validation
│  └─ Validate all user inputs
│
├─ API Security
│  ├─ HTTPS in production
│  ├─ CORS validation
│  └─ Error handling
│
├─ Data Security
│  ├─ No sensitive data in localStorage
│  ├─ No API keys in client code
│  └─ Secure headers
│
└─ XSS Prevention
   ├─ Content sanitization
   ├─ Safe string handling
   └─ CSP headers (via backend)
```

## Browser APIs Used

```
Web APIs
├─ MediaRecorder (Voice Input)
│  ├─ navigator.mediaDevices.getUserMedia()
│  ├─ MediaRecorder interface
│  └─ AudioContext
│
├─ Web Audio
│  └─ Audio element (playback)
│
├─ Storage
│  └─ localStorage (session persistence)
│
├─ Navigation
│  └─ navigator.onLine (connection status)
│
└─ Fetch/XMLHttpRequest
   └─ Axios (abstracted)
```

---

**Created**: September 2026
**Version**: 1.0.0
**Architecture Pattern**: Component-Based with Centralized State
