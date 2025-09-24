import { useRef, useEffect } from "react";
import { useChatStore } from "../store/chatStore";
import { ShieldEllipsis, CircleFadingArrowUp, Aperture } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useUIStore } from "../store/uiStore";



export default function ChatArea() {
  const { messages, isLoading, error, sendMessage, conversationId, drafts, setDraft } = useChatStore();
  const draft = conversationId ? drafts[conversationId] || "" : "";
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const userId = "test-user";

  // 요게 입력창
  const handleSend = async () => {
    if (!draft.trim() || !conversationId) return;
    await sendMessage(conversationId, userId, draft.trim());
    setDraft(conversationId, ""); // 전송 후 초기화

    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  // 최신응답으로 스크롤
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [isLoading]);


  // ✅ textarea 높이 자동 조절
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [draft]);

  const { openSource } = useUIStore();

  return (
    <div className="flex-1 flex flex-col max-w-[55rem] w-full bg-white relative mx-auto overflow-y-auto">
      {/* 메시지 영역 */}
      <div className="flex-1 p-4">
        
        {messages.length === 0 ? (
          // ✅ 새 대화 가이드 UI
          <div className="h-full flex flex-col items-center justify-center text-center text-gray-500 space-y-4">
            <h2 className="text-xl font-semibold">
              무엇을 도와드릴까요? 🤔
            </h2>
            <p className="text-sm">
              아래 예시 질문을 클릭해 대화를 시작해보세요.
            </p>
            <ul className="space-y-2 text-sm text-left">
              <li className="cursor-pointer hover:text-blue-500">
                📌 산업안전보건법에서 응급조치 의무는?
              </li>
              <li className="cursor-pointer hover:text-blue-500">
                📌 화재 발생 시 사업주의 책임은?
              </li>
              <li className="cursor-pointer hover:text-blue-500">
                📌 판례: 시설관리 중 사고 사례
              </li>
              <li className="cursor-pointer hover:text-blue-500">
                📌 검색: 산업안전보건법 개정 일정 알려줘
              </li>
            </ul>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              className={`mb-6 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "user" ? (
                <div className="ml-auto text-lg bg-blue-200 text-black font-semibold p-3 rounded-2xl inline-block max-w-[75%]">
                  {msg.content}
                </div>
              ) : (
                <div className="text-lg leading-8 max-w-none text-gray-800">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      a: ({ href, children }) => (
                        <span
                          onClick={() => href && openSource(href)}
                          className="inline-block my-1 p-2 rounded-lg border border-gray-200 bg-gray-200 text-gray-700 text-sm hover:bg-gray-300 hover:border-blue-400 hover:text-blue-600 cursor-pointer transition"
                        >
                          {children}
                        </span>
                      ),
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          )))}
        
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
      <div className="sticky bottom-5 w-full px-4 py-3">
        <div className="w-full mx-auto flex items-end gap-2 bg-gray-200 rounded-2xl px-3 py-2 shadow-2xl">
          <textarea
            ref={textareaRef}
            rows={1}
            value={draft}
            onChange={(e) => setDraft(conversationId!, e.target.value)}
            onKeyDown={(e) => {
              if (isLoading) return;
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="메시지를 입력하세요..."
            disabled={isLoading}
            className="flex-1 resize-none bg-transparent text-lg focus:outline-none leading-snug py-2 ml-2"
          />

          {!draft.trim() ? (
            <div className="p-2 text-gray-400">
              <ShieldEllipsis className="w-5 h-5" />
            </div>
          ) : (
            <div
              onClick={!isLoading ? handleSend : undefined}
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
