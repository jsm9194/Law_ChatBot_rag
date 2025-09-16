import { useState } from "react"

export default function ChatInput({ onSend }: { onSend: (msg: string) => void }) {
  const [message, setMessage] = useState("")

  const handleSend = () => {
    if (!message.trim()) return
    onSend(message)
    setMessage("")
  }

  return (
    <div className="sticky bottom-0 w-full bg-[#343541] border-t border-gray-700">
      <div className="max-w-3xl mx-auto flex items-center gap-2 p-4">
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          type="text"
          placeholder="무엇이든 물어보세요..."
          className="flex-1 px-4 py-3 bg-[#40414f] text-gray-100 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 placeholder-gray-400"
        />
        <button
          onClick={handleSend}
          className="p-3 bg-green-500 hover:bg-green-600 text-white rounded-lg"
        >
          ➤
        </button>
      </div>
    </div>
  )
}
