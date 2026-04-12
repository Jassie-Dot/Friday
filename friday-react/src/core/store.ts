import { create } from 'zustand';

export type AIState = 'idle' | 'listening' | 'thinking' | 'responding' | 'error';

export interface ChatMessage {
  id: string;
  role: 'user' | 'friday';
  text: string;
}

export interface ContextPanel {
  id: string;
  type: 'weather' | 'code' | 'command' | 'alert';
  title: string;
  content: string;
  timestamp: number;
}

interface StoreProps {
  // Presence and visual state
  state: AIState;
  audioLevel: number;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  
  // Data
  messages: ChatMessage[];
  panels: ContextPanel[];
  
  // Actions
  setState: (s: AIState) => void;
  setAudioLevel: (l: number) => void;
  setConnectionStatus: (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;
  addMessage: (role: 'user' | 'friday', text: string) => void;
  loadMessages: (messages: ChatMessage[]) => void;
  addPanel: (panel: Omit<ContextPanel, 'id' | 'timestamp'>) => void;
  removePanel: (id: string) => void;
}

export const useAIStore = create<StoreProps>((set) => ({
  state: 'idle',
  audioLevel: 0,
  connectionStatus: 'disconnected',
  
  messages: [],
  panels: [],
  
  setState: (state) => set({ state }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  
  addMessage: (role, text) => set((s) => {
    const newMessage = { id: Date.now().toString() + Math.random().toString(), role, text };
    // Keep only last 5 messages rendered for transient floating UI
    return { messages: [...s.messages.slice(-4), newMessage] };
  }),
  
  loadMessages: (messages) => set({ messages: messages.slice(-5) }),
  
  addPanel: (p) => set((s) => ({
    panels: [{ ...p, id: Date.now().toString(), timestamp: Date.now() }, ...s.panels].slice(0, 3)
  })),
  
  removePanel: (id) => set((s) => ({
    panels: s.panels.filter(p => p.id !== id)
  }))
}));
