import React from 'react';
import { BotType } from '@/store/conversationStore';
import { getBotDisplayName, getBotDescription } from '@/utils/helpers';
import styles from './BotSelector.module.css';

interface BotSelectorProps {
  currentBot: BotType;
  onBotChange: (bot: BotType) => void;
}

const BotSelector: React.FC<BotSelectorProps> = ({ currentBot, onBotChange }) => {
  const bots: BotType[] = ['bot1', 'bot2'];

  return (
    <div className={styles.botSelectorContainer}>
      <div className={styles.botSelectorWrapper}>
        {bots.map((bot) => (
          <button
            key={bot}
            className={`${styles.botTab} ${
              currentBot === bot ? styles.active : ''
            }`}
            onClick={() => onBotChange(bot)}
            title={getBotDescription(bot)}
          >
            <span className={styles.botIcon}>
              {bot === 'bot1' ? '📜' : '⚡'}
            </span>
            <div className={styles.botInfo}>
              <span className={styles.botName}>{getBotDisplayName(bot)}</span>
              <span className={styles.botSubtitle}>
                {bot === 'bot1'
                  ? 'قوانين ومواد قانونية'
                  : 'أحكام وقضايا سابقة'}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

export default BotSelector;
