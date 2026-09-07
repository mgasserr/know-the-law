# Quick Start Guide - Frontend Setup in 5 Minutes

## 🚀 TL;DR - Get Running Now

### 1. Install & Setup (2 minutes)
```bash
cd "d:\Final AI Project WE\frontend"
npm install
cp .env.example .env.local
```

### 2. Start Dev Server (1 minute)
```bash
npm run dev
```
✅ App opens at `http://localhost:3000`

### 3. Make it Talk to Backend
Edit `.env.local`:
```env
REACT_APP_API_URL=http://localhost:8000
```

### 4. Verify Everything Works
- ✅ See two bot tabs (📜 و ⚡)
- ✅ Chat window displays
- ✅ Input field ready
- ✅ Mic button available

**DONE!** 🎉

---

## 📱 What You Have

### Two Bots Ready
| Bot | Purpose | Status |
|-----|---------|--------|
| 📜 Bot 1 | Laws & Statutes | ✅ Ready |
| ⚡ Bot 2 | Cases & Precedents | ✅ Ready |

### Features Ready
- ✅ Text chat
- ✅ Voice input (mic icon)
- ✅ Citations display
- ✅ Responsive design
- ✅ Error handling
- ✅ Loading states

---

## 🔧 Common Commands

```bash
# Development server
npm run dev

# Production build
npm run build

# Preview build
npm run preview

# Type checking
npm run type-check
```

---

## 🎯 Next Steps

### For Backend Team
1. Implement endpoints in `API_INTEGRATION.md`
2. Test with frontend on `http://localhost:3000`
3. Verify CORS is enabled

### For Frontend Team
1. Backend integration testing
2. Set up CI/CD (GitHub Actions)
3. Configure production environment
4. Deploy to Vercel/Netlify

### For QA Team
1. Test all features
2. Test responsive design
3. Test on different browsers
4. Test error scenarios

---

## 📚 Key Documentation

| Doc | When to Read |
|-----|-------------|
| [README.md](README.md) | First time setup |
| [DEVELOPMENT.md](DEVELOPMENT.md) | During development |
| [API_INTEGRATION.md](API_INTEGRATION.md) | Backend integration |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Understanding design |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Going to production |
| [TESTING.md](TESTING.md) | Writing tests |

---

## ❓ Troubleshooting

### "Port 3000 already in use"
```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID [PID] /F

# Mac/Linux
lsof -i :3000
kill -9 [PID]
```

### "Backend connection failed"
1. Check backend is running on `:8000`
2. Verify `REACT_APP_API_URL` in `.env.local`
3. Check CORS settings

### "Microphone not working"
1. Check browser permissions
2. Check microphone is connected
3. Try in another browser

### "Nothing showing up"
```bash
npm run type-check  # Check errors
npm install         # Reinstall dependencies
npm run dev         # Restart dev server
```

---

## 📦 Technology Stack

- **Framework**: React 18
- **Language**: TypeScript
- **Build**: Vite
- **State**: Zustand
- **HTTP**: Axios
- **Styling**: CSS Modules + Global CSS
- **Icons**: React Icons

---

## 🌍 Browser Support

✅ Chrome, Firefox, Safari, Edge (latest 2 versions)
✅ Mobile browsers (iOS Safari, Chrome Mobile)

---

## 💾 Project Structure

```
Frontend/
├── src/components/    ← React components
├── src/services/      ← API client
├── src/store/         ← State management
├── src/utils/         ← Helper functions
├── src/styles/        ← Global CSS
└── docs/              ← Documentation
```

---

## 🔑 Key Files to Know

| File | Purpose |
|------|---------|
| `src/App.tsx` | Main app component |
| `src/services/chatbotAPI.ts` | API methods |
| `src/store/conversationStore.ts` | Global state |
| `.env.local` | Configuration |
| `vite.config.ts` | Build config |

---

## 🎨 Customization Quick Tips

### Change Bot Names
Edit `.env.local`:
```env
REACT_APP_BOT1_NAME=Your Bot 1 Name
REACT_APP_BOT2_NAME=Your Bot 2 Name
```

### Change Colors
Edit `src/styles/global.css`:
```css
:root {
  --primary: #your-color;
  --primary-light: #lighter-shade;
}
```

### Change API URL
Edit `.env.local`:
```env
REACT_APP_API_URL=https://your-api.com
```

---

## 📊 Performance

Expected metrics:
- ⚡ Initial load: < 2 seconds
- 📦 Bundle size: ~400-500 KB (gzipped)
- 🎯 Interactive: < 3.5 seconds

---

## 🆘 Getting Help

1. **Check Documentation** - Most answers in `*.md` files
2. **Read Error Messages** - They usually explain the issue
3. **Check Console** - Browser dev tools (F12)
4. **TypeScript Errors** - Run `npm run type-check`

---

## ✅ Verification Checklist

After setup, verify:
- [ ] `npm install` completes without errors
- [ ] `npm run dev` starts successfully
- [ ] App opens at `localhost:3000`
- [ ] Header shows "مستشار القوانين الذكي"
- [ ] Two bot tabs visible
- [ ] Chat window displays
- [ ] Mic button visible
- [ ] No console errors (F12)

---

## 🚀 Ready?

```bash
npm run dev
```

Now go build something amazing! 🎉

---

**Version**: 1.0.0
**Last Updated**: September 2026
