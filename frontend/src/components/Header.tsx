import React, { useState, useEffect } from 'react';
import { MdRefresh, MdInfo } from 'react-icons/md';
import styles from './Header.module.css';

interface HeaderProps {
  onClear: () => void;
  isLoading: boolean;
}

const Header: React.FC<HeaderProps> = ({ onClear, isLoading }) => {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return (
    <header className={styles.header}>
      <div className={styles.headerContent}>
        <div className={styles.logoSection}>
          <div className={styles.logoIcon}>⚖️</div>
          <div className={styles.logoText}>
            <h1 className={styles.appTitle}>مستشار القوانين الذكي</h1>
            <p className={styles.appSubtitle}>
              محرك بحث قانوني مدعوم بالذكاء الاصطناعي
            </p>
          </div>
        </div>

        <div className={styles.statusSection}>
          <div
            className={`${styles.statusIndicator} ${
              isOnline ? styles.online : styles.offline
            }`}
            title={isOnline ? 'متصل' : 'غير متصل'}
          >
            <span className={styles.statusDot}></span>
            <span className={styles.statusText}>
              {isOnline ? 'متصل' : 'غير متصل'}
            </span>
          </div>

          <button
            className={styles.headerButton}
            onClick={onClear}
            disabled={isLoading}
            title="مسح المحادثة"
            aria-label="مسح المحادثة"
          >
            <MdRefresh size={20} />
            <span>مسح</span>
          </button>

          <button
            className={styles.headerButton}
            title="حول التطبيق"
            aria-label="حول التطبيق"
          >
            <MdInfo size={20} />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
