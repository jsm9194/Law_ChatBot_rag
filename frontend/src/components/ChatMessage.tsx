interface ChatMessageProps {
  role: "user" | "assistant"
  text: string
  sourceUrl?: string
  onOpenSource?: (url: string) => void
}

export default function ChatMessage({ role, text, sourceUrl, onOpenSource }: ChatMessageProps) {
  const isUser = role === "user"
  return (
    <div className={`w-full ${isUser ? "bg-[#343541]" : "bg-[#444654]"} py-6 px-4`}>
      <div className="max-w-3xl mx-auto flex items-start space-x-4">
        {/* GPT는 아이콘 표시, 유저는 비움 */}
        {!isUser && (
          <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center text-white font-bold">
            G
          </div>
        )}
        <div className="flex-1 text-gray-100 whitespace-pre-wrap leading-relaxed">
          {text}
          {sourceUrl && (
            <button
              onClick={() => onOpenSource && onOpenSource(sourceUrl)}
              className="ml-2 text-sm text-blue-400 underline"
            >
              출처 보기
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
