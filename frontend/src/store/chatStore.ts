// 대화, 메시지 상태 관리용 Zustand 스토어
import { create } from "zustand";
import axios from "axios";

export interface Message {
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at?: string;
}

interface ChatState {
  conversations: Conversation[];
  conversationId: string | null;
  messages: Message[];
  isLoading: boolean; // ✅ 로딩 상태
  error: string | null; // ✅ 에러 메시지
  createConversation: (userId: string, title?: string) => Promise<void>;
  loadConversations: (userId: string) => Promise<void>;
  loadMessages: (conversationId: string) => Promise<void>;
  sendMessage: (conversationId: string, userId: string, content: string) => Promise<void>;
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  conversationId: null,
  messages: [],
  isLoading: false,
  error: null,

  // 새 대화 생성
  createConversation: async (userId, title) => {
    set({ isLoading: true, error: null });
    try {
      const res = await axios.post<{ conversation_id: string; title: string }>(
        "http://localhost:8000/conversation/new",
        { user_id: userId, title }
      );
      set({ conversationId: res.data.conversation_id, messages: [] });
      await useChatStore.getState().loadConversations(userId);
    } catch (err: any) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },

  // 대화 목록 불러오기
  loadConversations: async (userId) => {
    set({ isLoading: true, error: null });
    try {
      const res = await axios.get<Conversation[]>(`http://localhost:8000/conversations/${userId}`);
      set({ conversations: res.data });
    } catch (err: any) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },

  // 특정 대화 메시지 불러오기
  loadMessages: async (conversationId) => {
    set({ isLoading: true, error: null });
    try {
      const res = await axios.get<Message[]>(`http://localhost:8000/conversation/${conversationId}`);
      set({ conversationId, messages: res.data });
    } catch (err: any) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },

  // 메시지 보내기
  sendMessage: async (conversationId, userId, content) => {
    set({ isLoading: true, error: null });
    try {
      const userMsg: Message = { role: "user", content };
      set((state) => ({ messages: [...state.messages, userMsg] }));

      await axios.post("http://localhost:8000/message", {
        conversation_id: conversationId,
        user_id: userId,
        role: "user",
        content,
      });

      const res = await axios.post<{ answer: string }>("http://localhost:8000/ask", {
        conversation_id: conversationId,
        question: content,
      });

      const answer = res.data.answer;
      const assistantMsg: Message = { role: "assistant", content: answer };

      set((state) => ({ messages: [...state.messages, assistantMsg] }));

      await axios.post("http://localhost:8000/message", {
        conversation_id: conversationId,
        user_id: "bot",
        role: "assistant",
        content: answer,
      });
    } catch (err: any) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },
}));
