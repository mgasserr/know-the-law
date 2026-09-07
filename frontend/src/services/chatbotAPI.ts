import axios, { AxiosInstance } from 'axios';
import { BotType, Message, Citation } from '@/store/conversationStore';

const API_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) ||
  'http://localhost:8000';

const DEMO_MODE =
  (typeof import.meta !== 'undefined' &&
    import.meta.env?.VITE_DEMO_MODE === 'true') ||
  false;

interface ChatRequest {
  message: string;
  bot: BotType;
  conversationHistory?: Message[];
  sessionId?: string;
}

interface ChatResponse {
  id: string;
  role: 'assistant';
  content: string;
  citations?: Citation[];
  bot: BotType;
  timestamp: number;
}

interface TranscribeResponse {
  text: string;
}

interface HistoryResponse {
  sessionId: string;
  messages: Message[];
}

class ChatbotAPI {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      timeout: 5000,
    });
  }

  /**
   * Send a message to the selected bot
   */
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    if (DEMO_MODE) {
      return this.getDemoResponse(request);
    }

    try {
      const response = await this.api.post<ChatResponse>('/chat', request);
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  /**
   * Send a message to Bot 1 (Laws & Statutes)
   */
  async chatBot1(
    message: string,
    conversationHistory?: Message[],
    sessionId?: string
  ): Promise<ChatResponse> {
    return this.sendMessage({
      message,
      bot: 'bot1',
      conversationHistory,
      sessionId,
    });
  }

  /**
   * Send a message to Bot 2 (Cases & Precedents)
   */
  async chatBot2(
    message: string,
    conversationHistory?: Message[],
    sessionId?: string
  ): Promise<ChatResponse> {
    return this.sendMessage({
      message,
      bot: 'bot2',
      conversationHistory,
      sessionId,
    });
  }

  /**
   * Transcribe audio using Whisper
   */
  async transcribeAudio(audioBlob: Blob): Promise<string> {
    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, 'audio.wav');

      const response = await this.api.post<TranscribeResponse>(
        '/transcribe',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      return response.data.text;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  /**
   * Get conversation history (optional: for persistence)
   */
  async getConversationHistory(sessionId: string): Promise<Message[]> {
    try {
      const response = await this.api.get<HistoryResponse>(
        `/history/${sessionId}`
      );
      return response.data.messages;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  /**
   * Clear conversation history
   */
  async clearHistory(sessionId: string): Promise<void> {
    try {
      await this.api.delete(`/history/${sessionId}`);
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  /**
   * Generate TTS (Text-to-Speech) if enabled
   */
  async synthesizeSpeech(text: string, language: string = 'ar'): Promise<Blob> {
    try {
      const response = await this.api.post(
        '/tts',
        { text, language },
        { responseType: 'blob' }
      );
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  /**
   * Get bot info/status
   */
  async getBotInfo(bot: BotType): Promise<any> {
    try {
      const response = await this.api.get(`/bot/${bot}/info`);
      return response.data;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  /**
   * Health check for backend
   */
  async healthCheck(): Promise<boolean> {
    if (DEMO_MODE) {
      return true;
    }

    try {
      const response = await this.api.get('/health');
      return response.status === 200;
    } catch {
      return false;
    }
  }

  private getDemoResponse(request: ChatRequest): ChatResponse {
    const botLabel = request.bot === 'bot1' ? 'مستشار القوانين' : 'محلل الأحكام';

    const cannedReply =
      request.bot === 'bot1'
        ? `في وضع المعاينة، هذا مثال لرد ${botLabel}. يمكنني الإجابة عن مواد قانون المرافعات أو قانون مجلس الدولة، مع توضيح النصوص والمواد ذات الصلة.`
        : `في وضع المعاينة، هذا مثال لرد ${botLabel}. سأحلل الحكم أو القضية من خلال عرض المبدأ القانوني، وقائع القضية، والنتيجة المتوقعة.`;

    return {
      id: `demo-${Date.now()}`,
      role: 'assistant',
      content: cannedReply,
      bot: request.bot,
      timestamp: Date.now(),
      citations: [
        {
          id: `demo-citation-${Date.now()}`,
          text: request.bot === 'bot1' ? 'المادة 1 - قانون المرافعات' : 'الحكم رقم 2024/15',
          source: request.bot === 'bot1' ? 'قانون المرافعات' : 'قضية سابقة',
          type: request.bot === 'bot1' ? 'statute' : 'case',
          fullText:
            request.bot === 'bot1'
              ? 'هذا مثال توضيحي لمرجع قانوني يمكن استبداله بالبيانات الحقيقية من الخادم.'
              : 'هذا مثال توضيحي لمرجع قضائي يمكن استبداله بالبيانات الحقيقية من الخادم.',
        },
      ],
    };
  }

  private handleError(error: any): void {
    if (axios.isAxiosError(error)) {
      if (error.response) {
        console.error('API Error:', error.response.status, error.response.data);
      } else if (error.request) {
        console.error('No response from server:', error.request);
      } else {
        console.error('Error setting up request:', error.message);
      }
    } else {
      console.error('Unknown error:', error);
    }
  }
}

export const chatbotAPI = new ChatbotAPI();
