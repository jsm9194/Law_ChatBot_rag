import { useState, useRef, useEffect } from "react";
import { useChatStore } from "../store/chatStore";
import { ShieldEllipsis, CircleFadingArrowUp, Aperture } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";


export default function ChatArea() {
  const { messages, isLoading, error, sendMessage, conversationId } = useChatStore();
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const userId = "test-user";

  const handleSend = async () => {
    if (!input.trim() || !conversationId) return;
    await sendMessage(conversationId, userId, input.trim());
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"; // 전송 후 높이 초기화
    }
  };

  // 최신응답으로 스크롤
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);


  // ✅ textarea 높이 자동 조절
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [input]);

  return (
    <div className="flex-1 flex flex-col bg-white relative max-w-[40rem] mx-auto overflow-y-auto">
      {/* 메시지 영역 */}
      <div className="flex-1 p-4">
        {messages.map((msg, i) => (
          <div key={i} className="mb-6">
            {msg.role === "user" ? (
              <div className="ml-auto bg-blue-200 text-black font-semibold p-3 rounded-2xl max-w-[75%]">
                {msg.content}
              </div>
            ) : (
              <div className="prose prose-sm max-w-none text-gray-800">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        ))}

        {/* ✅ 로딩/에러 메시지 보존 */}
        {isLoading && (
          <span className="inline-flex items-center gap-2 text-gray-500 text-sm italic">
            응답 생성 중...
            <Aperture className="w-6 h-6 animate-spin" />
          </span>
        )}
        {error && <div className="text-red-500 text-sm">에러 발생: {error}</div>}

        {/* ✅ 자동 스크롤 포인트 */}
        <div ref={messagesEndRef} />
      </div>

      {/* ✅ 입력창 */}
      <div className="sticky bottom-5 px-4 py-3">
        <div className="w-full max-w-[40rem] mx-auto flex items-end gap-2 bg-gray-200 rounded-2xl px-3 py-2">
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="메시지를 입력하세요..."
          className="flex-1 resize-none bg-transparent text-sm focus:outline-none leading-snug py-2"
        />

        {!input.trim() ? (
          <div className="p-2 text-gray-400">
            <ShieldEllipsis className="w-5 h-5" />
          </div>
        ) : (
          <div
            onClick={handleSend}
            className="p-2 rounded-full bg-black text-white cursor-pointer hover:opacity-90 transition"
          >
            <CircleFadingArrowUp className="w-5 h-5" />
          </div>
        )}
      </div>
    </div>
    </div>
  );
}
