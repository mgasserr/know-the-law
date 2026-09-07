import React, { useEffect } from 'react';
import { useConversationStore, BotType } from '@/store/conversationStore';
import { chatbotAPI } from '@/services/chatbotAPI';
import { generateId } from '@/utils/helpers';
import Header from '@/components/Header';
import BotSelector from '@/components/BotSelector';
import ChatWindow from '@/components/ChatWindow';
import InputArea from '@/components/InputArea';
import styles from './App.module.css';

const App: React.FC = () => {
  const {
    currentBot,
    messages,
    isLoading,
    error,
    setCurrentBot,
    addMessage,
    setLoading,
    setError,
    clearConversation,
  } = useConversationStore();

  // Check backend connectivity on mount. Keep this fast so the UI still renders
  // while the backend is not connected yet.
  useEffect(() => {
    const checkConnection = async () => {
      const isHealthy = await chatbotAPI.healthCheck();
      if (!isHealthy) {
        setError(
          'لم يتمكن من الاتصال بالخادم. تأكد من تشغيل الخادم على http://localhost:8000'
        );
      }
    };

    void checkConnection();
  }, [setError]);

  const handleSendMessage = async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;

    try {
      setError(null);

      // Add user message
      const userMessage = {
        id: generateId(),
        role: 'user' as const,
        content: messageText,
        bot: currentBot,
        timestamp: Date.now(),
      };

      addMessage(userMessage);
      setLoading(true);

      // Send to appropriate bot
      const response =
        currentBot === 'bot1'
          ? await chatbotAPI.chatBot1(messageText, messages)
          : await chatbotAPI.chatBot2(messageText, messages);

      // Add assistant response
      const assistantMessage = {
        id: response.id,
        role: 'assistant' as const,
        content: response.content,
        bot: currentBot,
        timestamp: response.timestamp,
        citations: response.citations,
      };

      addMessage(assistantMessage);
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : 'حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.';

      setError(errorMessage);
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBotChange = (bot: BotType) => {
    if (bot !== currentBot) {
      setCurrentBot(bot);
    }
  };

  return (
    <div className={styles.app}>
      <Header onClear={clearConversation} isLoading={isLoading} />
      <BotSelector currentBot={currentBot} onBotChange={handleBotChange} />
      <ChatWindow messages={messages} isLoading={isLoading} error={error} />
      <InputArea onSendMessage={handleSendMessage} isLoading={isLoading} />
    </div>
  );
};

export default App;
