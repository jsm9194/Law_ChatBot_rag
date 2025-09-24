// store/chatStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
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
  isLoading: boolean;
  error: string | null;

  // 채팅방 선택
  setConversationId: (id: string) => void;

  // ✅ 대화방별 draft
  drafts: Record<string, string>;
  setDraft: (conversationId: string, val: string) => void;

  // ✅ 반환 타입을 Conversation 으로 변경
  createConversation: (userId: string, title?: string) => Promise<Conversation>;
  loadConversations: (userId: string) => Promise<void>;
  loadMessages: (conversationId: string) => Promise<void>;
  sendMessage: (conversationId: string, userId: string, content: string) => Promise<void>;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      conversations: [],
      conversationId: null,
      messages: [],
      isLoading: false,
      error: null,

      // ✅ draft 관리 (대화방별)
      drafts: {},
      setDraft: (conversationId, val) =>
        set((state) => ({
          drafts: { ...state.drafts, [conversationId]: val },
        })),

      setConversationId: (id) => set({ conversationId: id }),

      // 새 대화 생성
      createConversation: async (userId, title) => {
        set({ isLoading: true, error: null });
        try {
          const res = await axios.post<{ conversation_id: string; title: string }>(
            "http://localhost:8000/conversation/new",
            { user_id: userId, title }
          );

          const newConv: Conversation = {
            id: res.data.conversation_id,
            title: res.data.title,
            created_at: new Date().toISOString(),
          };

          set({ conversationId: newConv.id, messages: [] });
          await useChatStore.getState().loadConversations(userId);

          return newConv; // ✅ 이제 Sidebar에서 사용 가능
        } catch (err: any) {
          set({ error: err.message });
          throw err;
        } finally {
          set({ isLoading: false });
        }
      },

      // 대화 목록 불러오기
      loadConversations: async (userId) => {
        set({ isLoading: true, error: null });
        try {
          const res = await axios.get<Conversation[]>(
            `http://localhost:8000/conversations/${userId}`
          );
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
          const res = await axios.get<Message[]>(
            `http://localhost:8000/conversation/${conversationId}`
          );
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

          const res = await axios.post<{ answer: string }>(
            "http://localhost:8000/ask",
            {
              conversation_id: conversationId,
              question: content,
            }
          );

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
    }),
    { name: "chat-storage" } // ✅ localStorage key
  )
);
