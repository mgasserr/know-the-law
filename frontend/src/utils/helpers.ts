import { formatDistanceToNow } from 'date-fns';
import { ar } from 'date-fns/locale';

/**
 * Generate a unique message ID
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate a session ID (for backend persistence)
 */
export function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Format timestamp in Arabic
 */
export function formatArabicTime(timestamp: number): string {
  try {
    return formatDistanceToNow(new Date(timestamp), {
      addSuffix: true,
      locale: ar,
    });
  } catch {
    const date = new Date(timestamp);
    return date.toLocaleString('ar-EG');
  }
}

/**
 * Truncate text with ellipsis
 */
export function truncateText(text: string, maxLength: number = 100): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

/**
 * Extract citation references from text
 * Looks for patterns like "المادة 50" or "قضية رقم 1234"
 */
export function extractCitations(text: string): Array<{ text: string; index: number }> {
  const patterns = [
    /المادة\s+\d+/g, // المادة X
    /المواد\s+\d+/g, // المواد X
    /قضية\s+رقم\s+\d+/g, // قضية رقم X
    /الحكم\s+رقم\s+\d+/g, // الحكم رقم X
  ];

  const citations: Array<{ text: string; index: number }> = [];

  patterns.forEach((pattern) => {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      citations.push({
        text: match[0],
        index: match.index,
      });
    }
  });

  return citations.sort((a, b) => a.index - b.index);
}

/**
 * Determine bot type from string
 */
export function isBotType(value: string): value is 'bot1' | 'bot2' {
  return value === 'bot1' || value === 'bot2';
}

/**
 * Get bot display name
 */
export function getBotDisplayName(bot: 'bot1' | 'bot2'): string {
  const bot1Name =
    typeof import.meta !== 'undefined' && import.meta.env?.VITE_BOT1_NAME
      ? import.meta.env.VITE_BOT1_NAME
      : 'مستشار القوانين';

  const bot2Name =
    typeof import.meta !== 'undefined' && import.meta.env?.VITE_BOT2_NAME
      ? import.meta.env.VITE_BOT2_NAME
      : 'محلل الأحكام';

  return bot === 'bot1' ? bot1Name : bot2Name;
}

/**
 * Get bot description
 */
export function getBotDescription(bot: 'bot1' | 'bot2'): string {
  return bot === 'bot1'
    ? 'متخصص في البحث عن المواد القانونية والنقاط الأساسية في قانون المرافعات وقانون مجلس الدولة'
    : 'متخصص في تحليل الأحكام والقضايا السابقة وتقديم المبادئ القانونية المستقرة';
}
