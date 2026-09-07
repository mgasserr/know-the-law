import { create } from 'zustand';

export type BotType = 'bot1' | 'bot2';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  bot: BotType;
  timestamp: number;
  citations?: Citation[];
  audioUrl?: string;
}

export interface Citation {
  id: string;
  text: string;
  source: string; // e.g., "المادة 50 - قانون المرافعات" or "قضية رقم 1234"
  type: 'statute' | 'case'; // statue for Bot1, case for Bot2
  fullText?: string;
}

export interface ConversationState {
  currentBot: BotType;
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setCurrentBot: (bot: BotType) => void;
  addMessage: (message: Message) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearConversation: () => void;
  setMessages: (messages: Message[]) => void;
}

export const useConversationStore = create<ConversationState>((set) => ({
  currentBot: 'bot1',
  messages: [],
  isLoading: false,
  error: null,

  setCurrentBot: (bot) => set({ currentBot: bot, messages: [] }), // Clear messages when switching bots
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  clearConversation: () =>
    set({
      messages: [],
      error: null,
    }),
  setMessages: (messages) => set({ messages }),
}));
