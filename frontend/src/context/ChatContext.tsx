    import React, { createContext, useContext, useState } from "react";
    import axios from "axios";

    // ---------------------------
    // 타입 정의
    // ---------------------------
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

    interface ChatContextType {
    conversations: Conversation[];
    conversationId: string | null;
    messages: Message[];
    createConversation: (userId: string, title?: string) => Promise<void>;
    loadConversations: (userId: string) => Promise<void>;
    loadMessages: (conversationId: string) => Promise<void>;
    sendMessage: (conversationId: string, userId: string, content: string) => Promise<void>;
    }

    // ---------------------------
    // Context 생성
    // ---------------------------
    const ChatContext = createContext<ChatContextType | undefined>(undefined);

    export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);

    // 새 대화 생성
    const createConversation = async (userId: string, title?: string) => {
    const res = await axios.post<{ conversation_id: string; title: string }>(
        "http://localhost:8000/conversation/new",
        { user_id: userId, title }
    );
    setConversationId(res.data.conversation_id);
    setMessages([]); // 새 대화니까 메시지 초기화
    await loadConversations(userId);
    };

    // 대화 목록 불러오기
    const loadConversations = async (userId: string) => {
    const res = await axios.get<Conversation[]>(`http://localhost:8000/conversations/${userId}`);
    setConversations(res.data);
    };

    // 특정 대화 메시지 불러오기
    const loadMessages = async (conversationId: string) => {
    const res = await axios.get<Message[]>(`http://localhost:8000/conversation/${conversationId}`);
    setConversationId(conversationId);
    setMessages(res.data);
    };

    // 메시지 보내기
    const sendMessage = async (conversationId: string, userId: string, content: string) => {
    // 1. 사용자 메시지 UI에 반영 + DB 저장
    const userMsg: Message = { role: "user", content };
    setMessages((prev) => [...prev, userMsg]);

    await axios.post("http://localhost:8000/message", {
        conversation_id: conversationId,
        user_id: userId,
        role: "user",
        content,
    });

    // 2. GPT 답변 요청 (conversation_id 포함!)
    const res = await axios.post<{ answer: string }>("http://localhost:8000/ask", {
        conversation_id: conversationId,
        question: content,
    });

    const answer = res.data.answer;

    // 3. GPT 답변 UI에 반영 + DB 저장
    const assistantMsg: Message = { role: "assistant", content: answer };
    setMessages((prev) => [...prev, assistantMsg]);

    await axios.post("http://localhost:8000/message", {
        conversation_id: conversationId,
        user_id: "bot",
        role: "assistant",
        content: answer,
    });
    };

    return (
    <ChatContext.Provider
        value={{
        conversations,
        conversationId,
        messages,
        createConversation,
        loadConversations,
        loadMessages,
        sendMessage,
        }}
    >
        {children}
    </ChatContext.Provider>
    );
    };

    // ---------------------------
    // 훅: Context 사용
    // ---------------------------
    export const useChat = () => {
    const context = useContext(ChatContext);
    if (!context) throw new Error("useChat must be used within ChatProvider");
    return context;
    };
