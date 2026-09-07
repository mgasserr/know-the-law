# API Integration Guide

This document describes the API endpoints that the frontend expects from the backend.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, no authentication is required. Future versions may implement token-based authentication.

## API Endpoints

### 1. Chat Endpoint

Send a message to the chatbot and receive a response.

**Endpoint:** `POST /chat`

**Request Body:**
```json
{
  "message": "ما هي المادة 50 من قانون المرافعات؟",
  "bot": "bot1",
  "conversationHistory": [
    {
      "id": "msg-1",
      "role": "user",
      "content": "مرحبا",
      "bot": "bot1",
      "timestamp": 1693123456789
    }
  ],
  "sessionId": "session-1693123456789"
}
```

**Request Parameters:**
- `message` (string, required): The user's message
- `bot` (string, required): Either "bot1" or "bot2"
- `conversationHistory` (array, optional): Previous messages for context
- `sessionId` (string, optional): Session identifier for persistence

**Response:**
```json
{
  "id": "msg-2",
  "role": "assistant",
  "content": "المادة 50 من قانون المرافعات تتناول...",
  "bot": "bot1",
  "timestamp": 1693123457000,
  "citations": [
    {
      "id": "cite-1",
      "text": "المادة 50 - قانون المرافعات",
      "source": "المادة 50",
      "type": "statute",
      "fullText": "النص الكامل للمادة..."
    }
  ]
}
```

**Response Fields:**
- `id` (string): Unique message identifier
- `role` (string): Always "assistant"
- `content` (string): The bot's response
- `bot` (string): The bot that generated the response
- `timestamp` (number): Unix timestamp in milliseconds
- `citations` (array): References extracted from the response

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Invalid input
- `500 Internal Server Error`: Server error

### 2. Transcribe Audio Endpoint

Convert speech to text using Whisper.

**Endpoint:** `POST /transcribe`

**Request:**
- Content-Type: `multipart/form-data`
- Field: `audio` (file, required) - Audio file (WAV, MP3, OGG, etc.)

**Request Example:**
```bash
curl -X POST http://localhost:8000/transcribe \
  -F "audio=@recording.wav"
```

**Response:**
```json
{
  "text": "ما هي المادة 50 من قانون المرافعات؟"
}
```

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: No audio file provided
- `500 Internal Server Error`: Transcription failed

### 3. Get Conversation History Endpoint

Retrieve the conversation history for a session.

**Endpoint:** `GET /history/{sessionId}`

**Path Parameters:**
- `sessionId` (string, required): The session identifier

**Response:**
```json
{
  "sessionId": "session-1693123456789",
  "messages": [
    {
      "id": "msg-1",
      "role": "user",
      "content": "مرحبا",
      "bot": "bot1",
      "timestamp": 1693123456789
    },
    {
      "id": "msg-2",
      "role": "assistant",
      "content": "مرحبا، كيف يمكنني مساعدتك؟",
      "bot": "bot1",
      "timestamp": 1693123457000,
      "citations": []
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Success
- `404 Not Found`: Session not found
- `500 Internal Server Error`: Server error

### 4. Clear Conversation History Endpoint

Delete the conversation history for a session.

**Endpoint:** `DELETE /history/{sessionId}`

**Path Parameters:**
- `sessionId` (string, required): The session identifier

**Response:**
```json
{
  "message": "Conversation history cleared"
}
```

**Status Codes:**
- `200 OK`: Success
- `404 Not Found`: Session not found
- `500 Internal Server Error`: Server error

### 5. Text-to-Speech Endpoint

Generate audio from text (optional feature).

**Endpoint:** `POST /tts`

**Request Body:**
```json
{
  "text": "المادة 50 من قانون المرافعات",
  "language": "ar"
}
```

**Request Parameters:**
- `text` (string, required): The text to synthesize
- `language` (string, optional, default: "ar"): Language code (e.g., "ar", "en")

**Response:**
- Content-Type: `audio/wav` or `audio/mpeg`
- Body: Binary audio file

**Status Codes:**
- `200 OK`: Success
- `400 Bad Request`: Missing text parameter
- `500 Internal Server Error`: Synthesis failed

### 6. Get Bot Info Endpoint

Retrieve information about a specific bot.

**Endpoint:** `GET /bot/{botId}/info`

**Path Parameters:**
- `botId` (string, required): Either "bot1" or "bot2"

**Response:**
```json
{
  "botId": "bot1",
  "name": "مستشار القوانين",
  "description": "متخصص في البحث عن المواد القانونية",
  "version": "1.0.0",
  "model": "Qwen2.5-7B-Instruct",
  "capabilities": [
    "statute_search",
    "citation_retrieval",
    "legal_analysis"
  ],
  "lastUpdated": "2024-09-07T12:00:00Z"
}
```

**Status Codes:**
- `200 OK`: Success
- `404 Not Found`: Bot not found
- `500 Internal Server Error`: Server error

### 7. Health Check Endpoint

Check if the backend is running and healthy.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "ok",
  "timestamp": 1693123456789,
  "uptime": 3600
}
```

**Status Codes:**
- `200 OK`: Backend is healthy
- `503 Service Unavailable`: Backend is not ready

## Data Models

### Message

```typescript
interface Message {
  id: string;              // Unique identifier
  role: 'user' | 'assistant';
  content: string;         // The message text
  bot: 'bot1' | 'bot2';   // Which bot processed it
  timestamp: number;       // Unix timestamp in ms
  citations?: Citation[];  // Referenced sources
}
```

### Citation

```typescript
interface Citation {
  id: string;
  text: string;           // Display text (e.g., "المادة 50")
  source: string;         // Full reference (e.g., "المادة 50 - قانون المرافعات")
  type: 'statute' | 'case'; // Type of citation
  fullText?: string;      // Complete text of the statute/case
}
```

### ChatRequest

```typescript
interface ChatRequest {
  message: string;
  bot: 'bot1' | 'bot2';
  conversationHistory?: Message[];
  sessionId?: string;
}
```

### ChatResponse

```typescript
interface ChatResponse {
  id: string;
  role: 'assistant';
  content: string;
  citations?: Citation[];
  bot: 'bot1' | 'bot2';
  timestamp: number;
}
```

## Error Handling

All errors follow this format:

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "The provided message is empty",
    "details": {
      "field": "message",
      "reason": "required"
    }
  }
}
```

### Common Error Codes

- `INVALID_INPUT`: Request validation failed
- `BOT_NOT_FOUND`: Specified bot doesn't exist
- `SESSION_NOT_FOUND`: Session ID not found
- `TRANSCRIPTION_FAILED`: Audio transcription failed
- `SYNTHESIS_FAILED`: Text-to-speech synthesis failed
- `INTERNAL_ERROR`: Unexpected server error
- `SERVICE_UNAVAILABLE`: Backend service not ready

## Rate Limiting

Currently, no rate limiting is enforced. This may be added in future versions.

## CORS Policy

The frontend is expected to run on a different port than the backend. Ensure CORS is properly configured on the backend to allow requests from `http://localhost:3000`.

## WebSocket Support (Future)

For real-time streaming responses, WebSocket support may be added:

```
ws://localhost:8000/chat/stream
```

## Testing the API

### Using cURL

```bash
# Send a message to Bot 1
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "ما هي المادة 50 من قانون المرافعات؟",
    "bot": "bot1"
  }'

# Check health
curl http://localhost:8000/health

# Transcribe audio
curl -X POST http://localhost:8000/transcribe \
  -F "audio=@audio.wav"
```

### Using Python

```python
import requests

# Send a message
response = requests.post(
    'http://localhost:8000/chat',
    json={
        'message': 'ما هي المادة 50 من قانون المرافعات؟',
        'bot': 'bot1'
    }
)
print(response.json())
```

## Implementation Notes

1. **Timeout**: All requests should have a reasonable timeout (30 seconds recommended)
2. **Retry Logic**: Implement exponential backoff for failed requests
3. **Connection Pooling**: Reuse HTTP connections for better performance
4. **Error Recovery**: Display user-friendly error messages
5. **Offline Support**: Consider implementing offline mode with service workers

---

**Last Updated**: September 2026
**API Version**: 1.0.0
