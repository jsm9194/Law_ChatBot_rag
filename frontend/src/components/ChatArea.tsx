import { useState } from "react";
import { useChat } from "../context/ChatContext";

const ChatInput = () => {
  const { conversationId, sendMessage } = useChat();
  const [input, setInput] = useState("");
  const userId = "user1"; // 🚨 임시 값

  const handleSend = () => {
    if (conversationId && input.trim()) {
      sendMessage(conversationId, userId, input);
      setInput("");
    }
  };

  return (
    <div className="p-3 border-t">
      <input
        className="w-full border rounded p-2"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSend()}
        placeholder="메시지를 입력하세요..."
      />
    </div>
  );
};

export default ChatInput;
