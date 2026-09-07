import React, { useState, useRef, useEffect, useCallback } from "react";
import { Send, Loader2, AlertTriangle } from "lucide-react";

// -----------------------------------------------------------------------
// Configuration — point this at your FastAPI backend
// -----------------------------------------------------------------------
const API_BASE_URL = "http://localhost:8000";

const SUGGESTIONS = [
  "ما هي شروط صحة العقد؟",
  "متى ينتهي عقد الإيجار؟",
  "ما هو التعويض عن الضرر وفقاً لأحكام محكمة النقض؟",
  "ما هي حقوق الملكية الخاصة؟",
];

const SOURCES = [
  "القانون المدني المصري",
  "مختارات من أحكام محكمة النقض",
  "مبادئ قانونية صادرة عن محكمة النقض",
];

const CITATION_PATTERN = /(مادة\s*\d+)/g;

function renderAnswer(text) {
  const parts = text.split(CITATION_PATTERN);
  return parts.map((part, i) =>
    CITATION_PATTERN.test(part) ? (
      <span className="ktl-citation" key={i}>
        {part}
      </span>
    ) : (
      <React.Fragment key={i}>{part}</React.Fragment>
    )
  );
}

function Seal() {
  return (
    <svg viewBox="0 0 44 44" className="ktl-seal" aria-hidden="true">
      <circle cx="22" cy="22" r="19" className="ktl-seal-ring" />
      <circle cx="22" cy="22" r="14.5" className="ktl-seal-inner" />
      <path d="M13 22h18M22 13v18" className="ktl-seal-cross" />
      <circle cx="22" cy="22" r="3.2" className="ktl-seal-dot" />
    </svg>
  );
}

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [serverStatus, setServerStatus] = useState("checking"); // checking | ready | not-ready | offline

  const scrollRef = useRef(null);
  const textareaRef = useRef(null);
  const idRef = useRef(0);

  const nextId = () => {
    idRef.current += 1;
    return idRef.current;
  };

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/`)
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => {
        if (cancelled) return;
        setServerStatus(data.rag_ready ? "ready" : "not-ready");
      })
      .catch(() => {
        if (!cancelled) setServerStatus("offline");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isSending]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        160
      )}px`;
    }
  }, [input]);

  const statusLabel = {
    checking: "جاري التحقق من الاتصال",
    ready: "متصل بالخادم",
    "not-ready": "الخادم قيد التهيئة",
    offline: "غير متصل بالخادم",
  }[serverStatus];

  const sendQuestion = useCallback(
    async (question) => {
      const trimmed = question.trim();
      if (!trimmed || isSending) return;

      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", text: trimmed },
      ]);
      setInput("");
      setIsSending(true);

      try {
        const res = await fetch(`${API_BASE_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: trimmed }),
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "تعذّر الحصول على إجابة من الخادم.");
        }

        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          { id: nextId(), role: "bot", text: data.answer },
        ]);
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: "error",
            text:
              err.message ||
              "تعذّر الاتصال بالخادم القانوني. تأكد من تشغيله على العنوان الصحيح ثم أعد المحاولة.",
          },
        ]);
      } finally {
        setIsSending(false);
      }
    },
    [isSending]
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    sendQuestion(input);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuestion(input);
    }
  };

  return (
    <div className="ktl-app" dir="rtl" lang="ar">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');

        .ktl-app {
          --ink: #1c2430;
          --ink-soft: #2c3646;
          --paper: #e7e2d3;
          --paper-raised: #f1ede2;
          --paper-line: #d8d1bd;
          --brass: #ad8a3e;
          --brass-soft: #ecdfc0;
          --charcoal: #26241f;
          --muted: #6b6659;
          --seal-red: #7a2a2a;
          --seal-red-soft: #f1e2df;

          width: 100%;
          height: 100%;
          min-height: 640px;
          display: flex;
          flex-direction: column;
          background: var(--paper);
          color: var(--charcoal);
          font-family: 'IBM Plex Sans Arabic', sans-serif;
          box-sizing: border-box;
          overflow: hidden;
          border-radius: 14px;
          box-shadow: 0 1px 0 rgba(0,0,0,0.06);
        }
        .ktl-app *, .ktl-app *::before, .ktl-app *::after { box-sizing: border-box; }

        /* ---------- Header / letterhead ---------- */
        .ktl-header {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 18px 22px;
          background: var(--ink);
          border-bottom: 3px solid var(--brass);
        }
        .ktl-seal { width: 40px; height: 40px; flex-shrink: 0; }
        .ktl-seal-ring { fill: none; stroke: var(--brass); stroke-width: 1.4; }
        .ktl-seal-inner { fill: none; stroke: var(--brass); stroke-width: 1; opacity: 0.6; }
        .ktl-seal-cross { stroke: var(--brass); stroke-width: 1.4; }
        .ktl-seal-dot { fill: var(--brass); }

        .ktl-heading { display: flex; flex-direction: column; gap: 2px; }
        .ktl-title {
          font-family: 'Amiri', serif;
          font-weight: 700;
          font-size: 26px;
          color: #f4efe2;
          line-height: 1.1;
        }
        .ktl-subtitle {
          font-size: 13px;
          color: #b9c0cc;
          font-weight: 400;
        }

        .ktl-status {
          margin-inline-start: auto;
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12.5px;
          color: #c7cdd8;
          white-space: nowrap;
        }
        .ktl-status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--muted);
        }
        .ktl-status-dot.ready { background: #4f9d6e; }
        .ktl-status-dot.not-ready { background: var(--brass); }
        .ktl-status-dot.offline { background: var(--seal-red); }
        .ktl-status-dot.checking { background: #8b93a3; animation: ktl-pulse 1.4s ease-in-out infinite; }

        /* ---------- Message area ---------- */
        .ktl-body {
          flex: 1;
          overflow-y: auto;
          padding: 24px 22px;
          display: flex;
          flex-direction: column;
          gap: 16px;
          position: relative;
        }
        .ktl-body::-webkit-scrollbar { width: 8px; }
        .ktl-body::-webkit-scrollbar-thumb { background: var(--paper-line); border-radius: 4px; }

        .ktl-empty {
          margin: auto 0;
          text-align: center;
          max-width: 440px;
          margin-inline: auto;
        }
        .ktl-empty-title {
          font-family: 'Amiri', serif;
          font-size: 21px;
          font-weight: 700;
          color: var(--ink);
          margin-bottom: 8px;
        }
        .ktl-empty-text {
          font-size: 14px;
          color: var(--muted);
          line-height: 1.9;
          margin-bottom: 20px;
        }
        .ktl-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          justify-content: center;
        }
        .ktl-chip {
          border: 1px solid var(--paper-line);
          background: var(--paper-raised);
          color: var(--charcoal);
          font-family: inherit;
          font-size: 13px;
          padding: 8px 14px;
          border-radius: 8px;
          cursor: pointer;
          transition: border-color 0.15s ease, background 0.15s ease;
        }
        .ktl-chip:hover { border-color: var(--brass); background: var(--brass-soft); }
        .ktl-chip:focus-visible { outline: 2px solid var(--brass); outline-offset: 2px; }
        .ktl-sources {
          margin-top: 18px;
          font-size: 11.5px;
          color: var(--muted);
          border-top: 1px solid var(--paper-line);
          padding-top: 12px;
        }

        .ktl-row { display: flex; }
        .ktl-row.user { justify-content: flex-start; }
        .ktl-row.bot, .ktl-row.error { justify-content: flex-end; }

        .ktl-bubble {
          max-width: 78%;
          padding: 13px 16px;
          font-size: 15px;
          line-height: 1.95;
        }
        .ktl-bubble.user {
          background: var(--ink);
          color: #f2efe4;
          border-radius: 12px 12px 12px 3px;
        }
        .ktl-bubble.bot {
          background: var(--paper-raised);
          border: 1px solid var(--paper-line);
          border-inline-end: 3px solid var(--brass);
          border-radius: 12px 12px 3px 12px;
          font-family: 'Amiri', serif;
          font-size: 16.5px;
          color: var(--charcoal);
        }
        .ktl-bubble.error {
          background: var(--seal-red-soft);
          border: 1px solid #dcb9b4;
          border-inline-end: 3px solid var(--seal-red);
          border-radius: 12px 12px 3px 12px;
          color: #5c2323;
          display: flex;
          gap: 8px;
          align-items: flex-start;
          font-size: 14px;
        }
        .ktl-citation {
          background: var(--brass-soft);
          color: #6b511e;
          border-radius: 5px;
          padding: 1px 6px;
          font-family: 'IBM Plex Sans Arabic', sans-serif;
          font-weight: 600;
          font-size: 14px;
        }

        .ktl-thinking {
          display: flex;
          align-items: center;
          gap: 10px;
          color: var(--muted);
          font-size: 13.5px;
          padding: 4px 4px;
        }
        .ktl-dots { display: inline-flex; gap: 4px; }
        .ktl-dots span {
          width: 5px; height: 5px; border-radius: 50%;
          background: var(--brass);
          animation: ktl-bounce 1.1s ease-in-out infinite;
        }
        .ktl-dots span:nth-child(2) { animation-delay: 0.15s; }
        .ktl-dots span:nth-child(3) { animation-delay: 0.3s; }

        /* ---------- Composer ---------- */
        .ktl-composer {
          border-top: 1px solid var(--paper-line);
          background: var(--paper-raised);
          padding: 14px 18px;
        }
        .ktl-form {
          display: flex;
          align-items: flex-end;
          gap: 10px;
        }
        .ktl-textarea {
          flex: 1;
          resize: none;
          border: 1px solid var(--paper-line);
          border-radius: 10px;
          padding: 11px 14px;
          font-family: inherit;
          font-size: 14.5px;
          line-height: 1.6;
          color: var(--charcoal);
          background: #fff;
          max-height: 160px;
          min-height: 46px;
        }
        .ktl-textarea:focus-visible {
          outline: none;
          border-color: var(--brass);
          box-shadow: 0 0 0 3px var(--brass-soft);
        }
        .ktl-send {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          background: var(--ink);
          color: #f2efe4;
          border: none;
          border-radius: 10px;
          padding: 12px 18px;
          font-family: inherit;
          font-size: 14.5px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s ease;
          flex-shrink: 0;
        }
        .ktl-send:hover:not(:disabled) { background: var(--ink-soft); }
        .ktl-send:disabled { opacity: 0.55; cursor: not-allowed; }
        .ktl-send:focus-visible { outline: 2px solid var(--brass); outline-offset: 2px; }

        .ktl-disclaimer {
          margin-top: 10px;
          font-size: 11.5px;
          color: var(--muted);
          text-align: center;
        }

        .ktl-spin { animation: ktl-spin 0.8s linear infinite; }
        @keyframes ktl-spin { to { transform: rotate(360deg); } }

        @keyframes ktl-bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
          40% { transform: translateY(-4px); opacity: 1; }
        }
        @keyframes ktl-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.35; }
        }
        @media (prefers-reduced-motion: reduce) {
          .ktl-dots span, .ktl-status-dot.checking { animation: none; }
        }

        @media (max-width: 560px) {
          .ktl-header { padding: 14px 16px; }
          .ktl-title { font-size: 21px; }
          .ktl-subtitle { display: none; }
          .ktl-status span:last-child { display: none; }
          .ktl-body { padding: 18px 14px; }
          .ktl-bubble { max-width: 88%; }
          .ktl-composer { padding: 12px; }
        }
      `}</style>

      <header className="ktl-header">
        <Seal />
        <div className="ktl-heading">
          <span className="ktl-title">اعرف القانون</span>
          <span className="ktl-subtitle">
            مساعد استرشادي في القانون المصري وأحكام محكمة النقض
          </span>
        </div>
        <div className="ktl-status">
          <span className={`ktl-status-dot ${serverStatus}`} />
          <span>{statusLabel}</span>
        </div>
      </header>

      <div className="ktl-body" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="ktl-empty">
            <div className="ktl-empty-title">بماذا يمكنني إفادتك؟</div>
            <p className="ktl-empty-text">
              اطرح سؤالك القانوني، وستأتيك الإجابة مدعّمة بأرقام المواد
              القانونية والمبادئ القضائية ذات الصلة.
            </p>
            <div className="ktl-chips">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="ktl-chip"
                  onClick={() => sendQuestion(s)}
                >
                  {s}
                </button>
              ))}
            </div>
            <p className="ktl-sources">
              المصادر المعتمدة: {SOURCES.join(" · ")}
            </p>
          </div>
        )}

        {messages.map((m) => (
          <div className={`ktl-row ${m.role}`} key={m.id}>
            {m.role === "error" ? (
              <div className="ktl-bubble error">
                <AlertTriangle size={16} style={{ marginTop: 2, flexShrink: 0 }} />
                <span>{m.text}</span>
              </div>
            ) : (
              <div className={`ktl-bubble ${m.role}`}>
                {m.role === "bot" ? renderAnswer(m.text) : m.text}
              </div>
            )}
          </div>
        ))}

        {isSending && (
          <div className="ktl-row bot">
            <div className="ktl-thinking">
              <span>جاري البحث في نصوص القانون</span>
              <span className="ktl-dots">
                <span /><span /><span />
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="ktl-composer">
        <form className="ktl-form" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            className="ktl-textarea"
            placeholder="اكتب سؤالك القانوني هنا…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button
            type="submit"
            className="ktl-send"
            disabled={isSending || !input.trim()}
          >
            {isSending ? <Loader2 size={17} className="ktl-spin" /> : <Send size={17} />}
            <span>إرسال</span>
          </button>
        </form>
        <p className="ktl-disclaimer">
          الإجابات مستخلصة آليًا من نصوص القانون وأحكام محكمة النقض، ولا تُغني عن استشارة محامٍ مختص.
        </p>
      </div>
    </div>
  );
}

export default App;