import { create } from "zustand";
import { persist } from "zustand/middleware";
import axios, { AxiosError, isAxiosError } from "axios";

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

  // draft (대화방별 입력 저장)
  drafts: Record<string, string>;
  setDraft: (conversationId: string, val: string) => void;

  // API
  createConversation: (userId: string, title?: string) => Promise<Conversation>;
  loadConversations: (userId: string) => Promise<void>;
  loadMessages: (conversationId: string, offset?: number, limit?: number) => Promise<void>;
  sendMessage: (conversationId: string, userId: string, content: string) => Promise<void>;
  addMessage: (message: Message) => void;
}

// ✅ 공통 에러 핸들러
function handleAxiosError(err: unknown): string {
  if (isAxiosError(err)) {
    const axiosErr = err as AxiosError<{ detail?: string; message?: string }>;
    return (
      axiosErr.response?.data?.detail ||
      axiosErr.response?.data?.message ||
      `API 요청 실패 (${axiosErr.response?.status})`
    );
  } else if (err instanceof Error) {
    return err.message;
  }
  return "알 수 없는 오류";
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      conversations: [],
      conversationId: null,
      messages: [],
      isLoading: false,
      error: null,

      drafts: {},
      setDraft: (conversationId, val) =>
        set((state) => ({
          drafts: { ...state.drafts, [conversationId]: val },
        })),

      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message],
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

          return newConv;
        } catch (err: unknown) {
          set({ error: handleAxiosError(err) });
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
        } catch (err: unknown) {
          set({ error: handleAxiosError(err) });
        } finally {
          set({ isLoading: false });
        }
      },

      // 특정 대화 메시지 불러오기 (✅ 레이지 로딩 적용)
      loadMessages: async (conversationId, offset = 0, limit = 20) => {
        set({ isLoading: true, error: null });
        try {
          const res = await axios.get<Message[]>(
            `http://localhost:8000/conversation/${conversationId}?offset=${offset}&limit=${limit}`
          );

          set((state) => ({
            conversationId,
            messages:
              offset === 0
                ? res.data // ✅ 첫 로딩은 새로 세팅
                : [...res.data, ...state.messages], // ✅ 스크롤 로딩은 앞에 붙이기
          }));
        } catch (err: unknown) {
          set({ error: handleAxiosError(err) });
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
        } catch (err: unknown) {
          set({ error: handleAxiosError(err) });
        } finally {
          set({ isLoading: false });
        }
      },
    }),
    { name: "chat-storage" }
  )
);
