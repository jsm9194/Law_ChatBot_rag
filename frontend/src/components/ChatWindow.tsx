import React, { useEffect, useState } from "react";
import {
  getConversationLogs,
  saveMessage,
  askBot,
} from "../api/api";

type Message = {
  role: "user" | "assistant";
  content: string;
  created_at?: string;
};

export default function ChatWindow({ conversationId }: { conversationId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [limit, setLimit] = useState(10);
  const [input, setInput] = useState("");
  const userId = "test-user"; // 로그인 붙기 전까지 더미 값

  // 대화 로그 불러오기
  useEffect(() => {
    const fetchLogs = async () => {
      const logs = await getConversationLogs(conversationId, limit, 0);
      setMessages(logs);
    };
    fetchLogs();
  }, [conversationId, limit]);

  // 스크롤 이벤트 (상단 20% 도달 시 로딩)
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const scrollProgress = el.scrollTop / (el.scrollHeight - el.clientHeight);

    if (scrollProgress < 0.2) {
      setLimit((prev) => (prev < 30 ? prev + 10 : 30)); // 최대 30까지 확장
    }
  };

  // 메시지 전송
  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    // DB 저장 (사용자 메시지)
    await saveMessage(conversationId, userId, "user", input);

    // ✅ 최근 10개 대화 기록을 history로 전달
    const historyText = [...messages, userMessage]
      .slice(-10)
      .map((m) => `${m.role}: ${m.content}`)
      .join("\n");

    // 챗봇 호출
    const res = await askBot(input, historyText);
    const botMessage: Message = { role: "assistant", content: res.answer };
    setMessages((prev) => [...prev, botMessage]);

    // DB 저장 (챗봇 메시지)
    await saveMessage(conversationId, "bot", "assistant", res.answer);
  };

  return (
    <div className="flex flex-col h-full">
      {/* 메시지 영역 */}
      <div
        className="flex-1 overflow-y-auto p-4 space-y-3"
        onScroll={handleScroll}
      >
        {messages.map((m, i) => (
          <div
            key={i}
            className={`p-2 rounded-md max-w-xl ${
              m.role === "user" ? "bg-blue-100 self-end" : "bg-gray-100 self-start"
            }`}
          >
            {m.content}
          </div>
        ))}
      </div>

      {/* 입력창 */}
      <div className="border-t p-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="질문을 입력하세요..."
          className="flex-1 p-2 border rounded"
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
        />
        <button
          onClick={sendMessage}
          className="px-4 py-2 bg-blue-500 text-white rounded"
        >
          보내기
        </button>
      </div>
    </div>
  );
}
