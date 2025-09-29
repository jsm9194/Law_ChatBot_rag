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
    (set, get) => ({
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

      // 특정 대화 메시지 불러오기
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
                ? res.data
                : [...res.data, ...state.messages],
          }));
        } catch (err: unknown) {
          set({ error: handleAxiosError(err) });
        } finally {
          set({ isLoading: false });
        }
      },

      // 메시지 보내기 (스트리밍 적용)
      sendMessage: async (conversationId, userId, content) => {
        set({ isLoading: true, error: null });

        try {
          // 1. 유저 메시지 추가
          const userMsg: Message = { role: "user", content };
          set((state) => ({ messages: [...state.messages, userMsg] }));

          await axios.post("http://localhost:8000/message", {
            conversation_id: conversationId,
            user_id: userId,
            role: "user",
            content,
          });

          // 2. 어시스턴트 placeholder 추가
          let assistantIndex: number;
          set((state) => {
            assistantIndex = state.messages.length; // 유저 메시지 뒤
            return {
              messages: [...state.messages, { role: "assistant", content: "" }],
            };
          });

          // 3. 스트리밍 요청
          const res = await fetch("http://localhost:8000/ask_stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ conversation_id: conversationId, question: content }),
          });

          const reader = res.body?.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader!.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const parts = buffer.split("\n");
            buffer = parts.pop() || "";

            for (const part of parts) {
              if (!part.trim()) continue;
              const data = JSON.parse(part);

              if (data.type === "content") {
                // ✅ 토큰 단위로 답변 이어붙이기
                set((state) => {
                  const updated = [...state.messages];
                  updated[assistantIndex!] = {
                    role: "assistant",
                    content: (updated[assistantIndex!].content || "") + data.delta,
                  };
                  return { messages: updated };
                });
              } else if (data.type === "sources") {
                // ✅ 출처 데이터 별도 관리 가능 (state에 sources 추가하면 좋음)
                console.log("출처:", data.data);
              }
            }
          }

          // 4. 최종 어시스턴트 메시지를 DB에 저장
          const finalMsg = get().messages[assistantIndex!];
          await axios.post("http://localhost:8000/message", {
            conversation_id: conversationId,
            user_id: "bot",
            role: "assistant",
            content: finalMsg.content,
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
