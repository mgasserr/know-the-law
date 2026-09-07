# Frontend Development Setup Guide

## Quick Start

### Prerequisites

- Node.js v16 or higher
- npm v8 or higher
- Git

### Installation

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env.local
   ```

3. **Update `.env.local` with your configuration:**
   ```env
   REACT_APP_API_URL=http://localhost:8000
   REACT_APP_BOT1_NAME=مستشار القوانين
   REACT_APP_BOT2_NAME=محلل الأحكام
   REACT_APP_ENABLE_VOICE=true
   REACT_APP_ENABLE_TTS=false
   ```

4. **Start development server:**
   ```bash
   npm run dev
   ```

   The app will open at `http://localhost:3000`

## Project Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── Header.tsx
│   │   ├── BotSelector.tsx
│   │   ├── ChatWindow.tsx
│   │   ├── Message.tsx
│   │   ├── Citation.tsx
│   │   ├── InputArea.tsx
│   │   ├── VoiceInput.tsx
│   │   └── *.module.css     # Component styles
│   ├── services/
│   │   └── chatbotAPI.ts    # API client
│   ├── store/
│   │   └── conversationStore.ts  # State management
│   ├── styles/
│   │   └── global.css       # Global styles
│   ├── utils/
│   │   ├── audioRecorder.ts # Audio recording utility
│   │   └── helpers.ts       # Helper functions
│   ├── App.tsx              # Main component
│   └── main.tsx             # Entry point
├── public/                  # Static files
├── index.html               # HTML template
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript configuration
└── package.json             # Dependencies
```

## Key Technologies

- **React 18**: UI library
- **TypeScript**: Type safety
- **Zustand**: State management
- **Vite**: Build tool and dev server
- **Axios**: HTTP client
- **React Icons**: Icon library
- **Date-fns**: Date formatting
- **CSS Modules**: Scoped styling

## Development Workflow

### 1. Creating a New Component

```typescript
// src/components/MyComponent.tsx
import React from 'react';
import styles from './MyComponent.module.css';

interface MyComponentProps {
  title: string;
}

const MyComponent: React.FC<MyComponentProps> = ({ title }) => {
  return (
    <div className={styles.container}>
      <h1>{title}</h1>
    </div>
  );
};

export default MyComponent;
```

### 2. Creating Component Styles

```css
/* src/components/MyComponent.module.css */
.container {
  padding: 1rem;
  border-radius: 0.5rem;
  background-color: var(--neutral-100);
}
```

### 3. Using the Store

```typescript
import { useConversationStore } from '@/store/conversationStore';

function MyComponent() {
  const { messages, currentBot } = useConversationStore();
  
  return (
    <div>
      {messages.map(msg => (
        <p key={msg.id}>{msg.content}</p>
      ))}
    </div>
  );
}
```

### 4. Making API Calls

```typescript
import { chatbotAPI } from '@/services/chatbotAPI';

async function sendMessage() {
  try {
    const response = await chatbotAPI.chatBot1(
      'ما هي المادة 50؟',
      []
    );
    console.log(response);
  } catch (error) {
    console.error('Failed to send message:', error);
  }
}
```

## Styling Guidelines

### Color Palette

The app uses CSS variables defined in `global.css`:

```css
/* Primary colors */
--primary: #1e3a8a
--primary-light: #3b82f6
--primary-dark: #1e40af

/* Secondary colors */
--secondary: #7c3aed
--secondary-light: #a78bfa

/* Status colors */
--success: #10b981
--warning: #f59e0b
--error: #ef4444

/* Neutral colors */
--neutral-50: #f9fafb
--neutral-100: #f3f4f6
--neutral-200: #e5e7eb
/* ... up to neutral-900 */
```

### Spacing

```css
--spacing-xs: 0.25rem
--spacing-sm: 0.5rem
--spacing-md: 1rem
--spacing-lg: 1.5rem
--spacing-xl: 2rem
--spacing-2xl: 3rem
```

### Border Radius

```css
--radius-sm: 0.375rem
--radius-md: 0.5rem
--radius-lg: 0.75rem
--radius-xl: 1rem
```

### Shadows

```css
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
```

## RTL Support

The entire app is RTL-aware:

- `direction: rtl` is set on the `html` element
- Flexbox layouts use standard properties (start/end)
- Padding/margin follow RTL conventions

## Responsive Design

The app is mobile-first and responsive:

- Desktop (1024px+): Full layout
- Tablet (768px): Adjusted spacing and font sizes
- Mobile (480px): Simplified layout

Breakpoints are used in media queries:

```css
@media (max-width: 768px) {
  /* Tablet styles */
}

@media (max-width: 480px) {
  /* Mobile styles */
}
```

## Performance Optimization

### Code Splitting

Components are automatically code-split by Vite:

```typescript
import { lazy, Suspense } from 'react';

const ChatWindow = lazy(() => import('./ChatWindow'));

<Suspense fallback={<div>Loading...</div>}>
  <ChatWindow />
</Suspense>
```

### Memoization

Use `React.memo` for expensive components:

```typescript
const Message = React.memo(({ message }) => {
  return <div>{message.content}</div>;
});
```

### Image Optimization

Keep images optimized and use appropriate formats:

- PNG for icons
- WebP for photos (with fallback)
- SVG for logos

## Testing

Currently, no testing framework is set up. To add tests:

```bash
npm install --save-dev @testing-library/react @testing-library/jest-dom vitest
```

## Building for Production

```bash
npm run build
```

Output will be in the `dist/` folder.

### Optimize Bundle Size

```bash
npm run build -- --sourcemap
```

Analyze the bundle:

```bash
npm install --save-dev rollup-plugin-visualizer
```

Then check the generated `dist/stats.html`.

## Environment Variables

### Development

Create `.env.local`:

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_BOT1_NAME=مستشار القوانين
REACT_APP_BOT2_NAME=محلل الأحكام
REACT_APP_ENABLE_VOICE=true
REACT_APP_ENABLE_TTS=false
```

### Production

Update the `.env` file before building:

```env
REACT_APP_API_URL=https://api.example.com
REACT_APP_BOT1_NAME=مستشار القوانين
REACT_APP_BOT2_NAME=محلل الأحكام
REACT_APP_ENABLE_VOICE=true
REACT_APP_ENABLE_TTS=false
```

## Debugging

### Browser DevTools

- Open DevTools: F12
- React DevTools extension recommended
- Redux DevTools for Zustand

### Console Logging

```typescript
console.log('Debug info:', data);
console.error('Error:', error);
```

### Network Debugging

- Open Network tab in DevTools
- Monitor API calls to the backend
- Check request/response payloads

## Common Issues

### Issue: Port 3000 already in use

**Solution:**
```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :3000
kill -9 <PID>
```

### Issue: Microphone not working

**Solution:**
1. Check browser permissions
2. Ensure HTTPS in production
3. Check microphone is connected
4. Test with system settings

### Issue: Backend connection failed

**Solution:**
1. Ensure backend is running on port 8000
2. Check `REACT_APP_API_URL` in `.env.local`
3. Check CORS settings on backend
4. Verify network connectivity

### Issue: TypeScript errors

**Solution:**
```bash
npm run type-check
```

Review errors and fix type mismatches.

## Git Workflow

1. Create a new branch:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make changes and commit:
   ```bash
   git add .
   git commit -m "Add feature description"
   ```

3. Push to remote:
   ```bash
   git push origin feature/my-feature
   ```

4. Create a pull request

## Additional Resources

- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Vite Documentation](https://vitejs.dev)
- [Zustand Documentation](https://github.com/pmndrs/zustand)
- [CSS Modules](https://github.com/css-modules/css-modules)

## Support

For questions or issues, contact the development team.

---

**Last Updated**: September 2026
**Version**: 1.0.0
