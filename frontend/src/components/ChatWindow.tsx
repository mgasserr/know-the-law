import React, { useEffect, useRef } from 'react';
import { Message } from '@/store/conversationStore';
import MessageComponent from './Message';
import styles from './ChatWindow.module.css';

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isLoading, error }) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className={styles.chatWindow}>
        <div className={styles.emptyState}>
          <div className={styles.emptyStateIcon}>⚖️</div>
          <h2 className={styles.emptyStateTitle}>
            مرحبا بك في مستشار القوانين الذكي
          </h2>
          <p className={styles.emptyStateSubtitle}>
            اختر الموضوع أدناه واطرح سؤالك
          </p>
          <div className={styles.suggestionsContainer}>
            <div className={styles.suggestionBox}>
              <h3>📜 قانون المرافعات</h3>
              <p>ابحث عن المواد القانونية والمبادئ الأساسية</p>
            </div>
            <div className={styles.suggestionBox}>
              <h3>⚡ أحكام القضاء</h3>
              <p>استكشف الأحكام والقضايا السابقة</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.chatWindow} ref={chatContainerRef}>
      {error && (
        <div className={styles.errorBanner}>
          <span className={styles.errorIcon}>⚠️</span>
          <span className={styles.errorMessage}>{error}</span>
        </div>
      )}

      <div className={styles.messagesContainer}>
        {messages.map((message) => (
          <MessageComponent key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className={styles.loadingContainer}>
            <div className={styles.loadingDots}>
              <span></span>
              <span></span>
              <span></span>
            </div>
            <p className={styles.loadingText}>جاري البحث والتحليل...</p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default ChatWindow;
