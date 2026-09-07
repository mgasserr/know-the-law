import React, { useState } from 'react';
import { Citation } from '@/store/conversationStore';
import styles from './Citation.module.css';

interface CitationProps {
  citation: Citation;
}

const CitationComponent: React.FC<CitationProps> = ({ citation }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleToggleExpand = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsExpanded(!isExpanded);
  };

  const getBadgeClass = () => {
    return citation.type === 'statute' ? styles.statuteBadge : styles.caseBadge;
  };

  const getBadgeLabel = () => {
    return citation.type === 'statute' ? 'مادة قانونية' : 'حكم قضائي';
  };

  return (
    <div className={styles.citationContainer}>
      <button
        className={`${styles.citationChip} ${getBadgeClass()}`}
        onClick={handleToggleExpand}
        title={citation.source}
      >
        <span className={styles.citationText}>{citation.source}</span>
        {citation.fullText && (
          <span className={styles.expandIcon}>
            {isExpanded ? '▼' : '▶'}
          </span>
        )}
      </button>

      {isExpanded && citation.fullText && (
        <div className={styles.expandedContent}>
          <p className={styles.fullText}>{citation.fullText}</p>
        </div>
      )}
    </div>
  );
};

export default CitationComponent;
