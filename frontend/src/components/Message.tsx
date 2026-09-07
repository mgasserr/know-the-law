import React from 'react';
import { Message } from '@/store/conversationStore';
import CitationComponent from './Citation';
import { formatArabicTime } from '@/utils/helpers';
import styles from './Message.module.css';

interface MessageProps {
  message: Message;
}

const MessageComponent: React.FC<MessageProps> = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`${styles.messageWrapper} ${isUser ? styles.userMessage : styles.assistantMessage}`}>
      <div className={styles.messageContainer}>
        <div className={styles.messageBubble}>
          <div className={styles.messageContent}>
            <p className={styles.messageText}>{message.content}</p>
            
            {message.citations && message.citations.length > 0 && (
              <div className={styles.citationsWrapper}>
                <div className={styles.citationsLabel}>المراجع:</div>
                <div className={styles.citationsList}>
                  {message.citations.map((citation) => (
                    <CitationComponent
                      key={citation.id}
                      citation={citation}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className={styles.messageFooter}>
            <span className={styles.timestamp}>
              {formatArabicTime(message.timestamp)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageComponent;
