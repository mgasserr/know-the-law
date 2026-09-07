# Frontend Testing Strategy & Guidelines

## Test Types Overview

### Unit Tests
Test individual functions, components, and modules in isolation.

### Integration Tests
Test how multiple components work together.

### End-to-End (E2E) Tests
Test complete user flows from UI interaction to API response.

### Performance Tests
Test speed, memory usage, and bundle size.

## Testing Setup (Future)

### Install Testing Libraries
```bash
npm install --save-dev \
  @testing-library/react \
  @testing-library/jest-dom \
  @testing-library/user-event \
  vitest \
  jsdom
```

### Vite Config Update
```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

## Unit Test Examples

### Testing a Utility Function
```typescript
// src/utils/helpers.test.ts
import { describe, it, expect } from 'vitest';
import { truncateText, generateId, isBotType } from './helpers';

describe('helpers', () => {
  describe('truncateText', () => {
    it('should truncate text longer than max length', () => {
      const text = 'This is a long text that needs truncation';
      const result = truncateText(text, 20);
      
      expect(result).toBe('This is a long text ...');
      expect(result.length).toBeLessThanOrEqual(23);
    });

    it('should not truncate text shorter than max length', () => {
      const text = 'Short text';
      const result = truncateText(text, 20);
      
      expect(result).toBe('Short text');
    });
  });

  describe('generateId', () => {
    it('should generate unique IDs', () => {
      const id1 = generateId();
      const id2 = generateId();
      
      expect(id1).not.toBe(id2);
    });

    it('should generate string IDs', () => {
      const id = generateId();
      
      expect(typeof id).toBe('string');
      expect(id.length).toBeGreaterThan(0);
    });
  });

  describe('isBotType', () => {
    it('should return true for valid bot types', () => {
      expect(isBotType('bot1')).toBe(true);
      expect(isBotType('bot2')).toBe(true);
    });

    it('should return false for invalid bot types', () => {
      expect(isBotType('bot3')).toBe(false);
      expect(isBotType('invalid')).toBe(false);
      expect(isBotType('')).toBe(false);
    });
  });
});
```

### Testing a Component
```typescript
// src/components/Citation.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Citation from './Citation';
import { Citation as CitationType } from '@/store/conversationStore';

describe('Citation Component', () => {
  const mockCitation: CitationType = {
    id: 'cite-1',
    text: 'المادة 50',
    source: 'المادة 50 - قانون المرافعات',
    type: 'statute',
    fullText: 'نص كامل للمادة...',
  };

  it('should render citation chip', () => {
    render(<Citation citation={mockCitation} />);
    
    const chip = screen.getByRole('button');
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent('المادة 50 - قانون المرافعات');
  });

  it('should expand on click', async () => {
    const user = userEvent.setup();
    render(<Citation citation={mockCitation} />);
    
    const button = screen.getByRole('button');
    await user.click(button);
    
    const fullText = screen.getByText('نص كامل للمادة...');
    expect(fullText).toBeInTheDocument();
  });

  it('should apply statute badge class', () => {
    const { container } = render(<Citation citation={mockCitation} />);
    
    const chip = container.querySelector('.statuteBadge');
    expect(chip).toBeInTheDocument();
  });
});
```

### Testing the Store
```typescript
// src/store/conversationStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useConversationStore } from './conversationStore';

describe('ConversationStore', () => {
  beforeEach(() => {
    // Reset store before each test
    useConversationStore.setState({
      currentBot: 'bot1',
      messages: [],
      isLoading: false,
      error: null,
    });
  });

  it('should initialize with default state', () => {
    const state = useConversationStore.getState();
    
    expect(state.currentBot).toBe('bot1');
    expect(state.messages).toEqual([]);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBe(null);
  });

  it('should change current bot', () => {
    const { setCurrentBot } = useConversationStore.getState();
    
    setCurrentBot('bot2');
    
    const state = useConversationStore.getState();
    expect(state.currentBot).toBe('bot2');
  });

  it('should add message', () => {
    const { addMessage } = useConversationStore.getState();
    
    const message = {
      id: 'msg-1',
      role: 'user' as const,
      content: 'Test message',
      bot: 'bot1' as const,
      timestamp: Date.now(),
    };
    
    addMessage(message);
    
    const state = useConversationStore.getState();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0]).toEqual(message);
  });

  it('should set loading state', () => {
    const { setLoading } = useConversationStore.getState();
    
    setLoading(true);
    
    let state = useConversationStore.getState();
    expect(state.isLoading).toBe(true);
    
    setLoading(false);
    
    state = useConversationStore.getState();
    expect(state.isLoading).toBe(false);
  });

  it('should clear conversation', () => {
    const { addMessage, clearConversation } = useConversationStore.getState();
    
    addMessage({
      id: 'msg-1',
      role: 'user',
      content: 'Test',
      bot: 'bot1',
      timestamp: Date.now(),
    });
    
    clearConversation();
    
    const state = useConversationStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.error).toBe(null);
  });
});
```

## Integration Test Examples

### Testing API Integration
```typescript
// src/services/chatbotAPI.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { chatbotAPI } from './chatbotAPI';
import axios from 'axios';

vi.mock('axios');

describe('ChatbotAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should send message to bot1', async () => {
    const mockResponse = {
      data: {
        id: 'msg-1',
        role: 'assistant',
        content: 'Response text',
        bot: 'bot1',
        timestamp: Date.now(),
      },
    };

    vi.mocked(axios.create().post).mockResolvedValue(mockResponse);

    const response = await chatbotAPI.chatBot1('Test message');
    
    expect(response).toEqual(mockResponse.data);
  });

  it('should handle transcription', async () => {
    const mockBlob = new Blob(['audio'], { type: 'audio/wav' });
    const mockResponse = {
      data: { text: 'Transcribed text' },
    };

    vi.mocked(axios.create().post).mockResolvedValue(mockResponse);

    const text = await chatbotAPI.transcribeAudio(mockBlob);
    
    expect(text).toBe('Transcribed text');
  });

  it('should handle health check', async () => {
    const mockResponse = { status: 200 };
    
    vi.mocked(axios.create().get).mockResolvedValue(mockResponse);

    const isHealthy = await chatbotAPI.healthCheck();
    
    expect(isHealthy).toBe(true);
  });
});
```

### Testing Component with Store
```typescript
// src/components/ChatWindow.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ChatWindow from './ChatWindow';

describe('ChatWindow Component', () => {
  it('should display empty state when no messages', () => {
    render(
      <ChatWindow
        messages={[]}
        isLoading={false}
        error={null}
      />
    );
    
    const emptyState = screen.getByText('مرحبا بك في مستشار القوانين الذكي');
    expect(emptyState).toBeInTheDocument();
  });

  it('should display messages', () => {
    const messages = [
      {
        id: 'msg-1',
        role: 'user' as const,
        content: 'User message',
        bot: 'bot1' as const,
        timestamp: Date.now(),
      },
      {
        id: 'msg-2',
        role: 'assistant' as const,
        content: 'Bot response',
        bot: 'bot1' as const,
        timestamp: Date.now(),
      },
    ];

    render(
      <ChatWindow
        messages={messages}
        isLoading={false}
        error={null}
      />
    );
    
    expect(screen.getByText('User message')).toBeInTheDocument();
    expect(screen.getByText('Bot response')).toBeInTheDocument();
  });

  it('should show error banner', () => {
    render(
      <ChatWindow
        messages={[]}
        isLoading={false}
        error="Test error message"
      />
    );
    
    expect(screen.getByText('Test error message')).toBeInTheDocument();
  });

  it('should show loading indicator', () => {
    render(
      <ChatWindow
        messages={[]}
        isLoading={true}
        error={null}
      />
    );
    
    expect(screen.getByText('جاري البحث والتحليل...')).toBeInTheDocument();
  });
});
```

## E2E Test Examples

### Testing Complete User Flow
```typescript
// tests/e2e/chat-flow.test.ts
import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '@/App';

describe('Chat Flow E2E', () => {
  it('should complete a full chat cycle', async () => {
    const user = userEvent.setup();
    
    render(<App />);
    
    // Wait for app to load
    await waitFor(() => {
      expect(screen.getByText('مستشار القوانين الذكي')).toBeInTheDocument();
    });
    
    // Type message
    const textarea = screen.getByPlaceholderText(/اكتب سؤالك/);
    await user.type(textarea, 'ما هي المادة 50؟');
    
    // Click send
    const sendButton = screen.getByRole('button', { name: /إرسال/ });
    await user.click(sendButton);
    
    // Wait for response
    await waitFor(() => {
      expect(screen.getByText(/المادة 50/)).toBeInTheDocument();
    });
    
    // Verify message is displayed
    expect(screen.getByText('ما هي المادة 50؟')).toBeInTheDocument();
  });

  it('should switch between bots', async () => {
    const user = userEvent.setup();
    
    render(<App />);
    
    const bot2Tab = screen.getByText('محلل الأحكام');
    await user.click(bot2Tab);
    
    expect(bot2Tab.closest('button')).toHaveClass('active');
  });
});
```

## Manual Testing Checklist

### UI Testing
- [ ] Header displays correctly
- [ ] Bot selector shows both bots
- [ ] Chat window scrolls smoothly
- [ ] Messages display with correct styling
- [ ] Citations expand/collapse
- [ ] Input area auto-resizes
- [ ] Voice button shows correct states

### Functionality Testing
- [ ] Send text message
- [ ] Record voice message
- [ ] Switch between bots
- [ ] Clear conversation
- [ ] Display error messages
- [ ] Show loading indicator
- [ ] Scroll to latest message

### Responsive Testing
- [ ] Desktop (1920x1080)
- [ ] Tablet (768x1024)
- [ ] Mobile (375x667)
- [ ] Mobile landscape (667x375)
- [ ] Tablet landscape (1024x768)

### Browser Testing
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Chrome Mobile (latest)
- [ ] Safari Mobile (latest)

### Accessibility Testing
- [ ] Keyboard navigation
- [ ] Screen reader compatibility
- [ ] Color contrast ratios
- [ ] ARIA labels
- [ ] Focus indicators
- [ ] Tab order

### Performance Testing
- [ ] Initial load time
- [ ] Message sending latency
- [ ] Scrolling performance
- [ ] Memory usage
- [ ] CPU usage
- [ ] Network requests

## Performance Benchmarks

Target metrics:
- **First Contentful Paint (FCP)**: < 2 seconds
- **Largest Contentful Paint (LCP)**: < 3 seconds
- **Cumulative Layout Shift (CLS)**: < 0.1
- **Time to Interactive (TTI)**: < 3.5 seconds
- **Bundle Size (gzipped)**: < 500 KB

## Continuous Integration Setup

### GitHub Actions Workflow
```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
        with:
          node-version: '18'
      
      - run: cd frontend && npm ci
      - run: cd frontend && npm run type-check
      - run: cd frontend && npm run build
      # Add test command when tests are set up
      # - run: cd frontend && npm run test
```

## Testing Best Practices

1. **Test Behavior, Not Implementation**
   - Test what users see and do
   - Not internal component state

2. **Use Descriptive Test Names**
   - Should read like documentation
   - Clearly state what's being tested

3. **Keep Tests Isolated**
   - Each test should be independent
   - Use `beforeEach` to set up state

4. **Mock External Dependencies**
   - Mock API calls
   - Mock browser APIs
   - Keep tests fast and reliable

5. **Write Testable Code**
   - Separate logic from UI
   - Use pure functions
   - Export utilities for testing

6. **Test Edge Cases**
   - Empty states
   - Error conditions
   - Boundary values
   - User errors

7. **Maintain Test Suite**
   - Update tests when code changes
   - Remove flaky tests
   - Keep coverage above 80%

---

**Created**: September 2026
**Version**: 1.0.0
**Status**: Ready for Implementation
