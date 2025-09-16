import ChatMessage from "./ChatMessage"
import ChatInput from "./ChatInput"
import { useState } from "react"
import { askBackend } from "../api/chat"

interface Message {
  role: "user" | "assistant"
  text: string
}

export default function ChatArea() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  const handleSend = async (msg: string) => {
    setMessages((prev) => [...prev, { role: "user", text: msg }])
    setLoading(true)

    try {
      const answer = await askBackend(msg)
      setMessages((prev) => [...prev, { role: "assistant", text: answer }])
    } catch (err) {
      console.error(err)
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "⚠️ 서버 요청 중 오류 발생" },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col bg-gray-50">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((m, i) => (
          <ChatMessage key={i} {...m} />
        ))}
        {loading && <p className="text-gray-400">답변 생성 중...</p>}
      </div>
      <ChatInput onSend={handleSend} />
    </div>
  )
}
