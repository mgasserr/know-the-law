import React, { useRef, useState } from 'react';
import { MdSend } from 'react-icons/md';
import VoiceInput from './VoiceInput';
import styles from './InputArea.module.css';

interface InputAreaProps {
  onSendMessage: (message: string) => void;
  isLoading?: boolean;
}

const InputArea: React.FC<InputAreaProps> = ({ onSendMessage, isLoading = false }) => {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSendMessage = () => {
    if (message.trim() && !isLoading) {
      onSendMessage(message.trim());
      setMessage('');
      
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Send on Enter, but allow Shift+Enter for new line
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);

    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(
        textareaRef.current.scrollHeight,
        120
      ) + 'px';
    }
  };

  const handleTranscriptionComplete = (text: string) => {
    setMessage((prev) => (prev ? `${prev} ${text}` : text));
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className={styles.inputAreaContainer}>
      <div className={styles.inputWrapper}>
        <VoiceInput
          onTranscriptionComplete={handleTranscriptionComplete}
          disabled={isLoading}
        />

        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder="اكتب سؤالك هنا... (أو استخدم الميكروفون)"
          value={message}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={1}
        />

        <button
          className={styles.sendButton}
          onClick={handleSendMessage}
          disabled={!message.trim() || isLoading}
          title={isLoading ? 'جاري المعالجة...' : 'إرسال'}
          aria-label="إرسال الرسالة"
        >
          <MdSend size={20} />
        </button>
      </div>

      <p className={styles.hint}>
        💡 نصيحة: اضغط Shift + Enter لسطر جديد
      </p>
    </div>
  );
};

export default InputArea;
