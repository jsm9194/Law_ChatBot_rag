import { useRef, useEffect, useState } from "react";
import { useChatStore } from "../store/chatStore";
import { ShieldEllipsis, CircleFadingArrowUp, Aperture, ChevronDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useUIStore } from "../store/uiStore";
import { useScrollToBottom } from "./hooks/useScrollToBottom";

/* 👇 스트리밍/저장 API */
import { askStream, saveMessage } from "../api/api";

/* 👇 서버가 내려주는 출처(Source) 타입(필요에 따라 필드 추가 가능) */
type Source = {
  law?: string;
  article?: string;
  url?: string;
  // 다른 키가 올 수 있으니 확장 허용
  [key: string]: unknown;
};

const USE_STREAMING = true; // 필요 시 false로 바꾸면 논-스트림 경로 사용

export default function ChatArea() {
  const {
    messages,
    isLoading,
    error,
    sendMessage,
    conversationId,
    drafts,
    setDraft,
    addMessage,
  } =
    useChatStore();
  const draft = conversationId ? drafts[conversationId] || "" : "";

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const textareaWrapperRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { showScrollButton, scrollToBottom } = useScrollToBottom(
    containerRef,
    messagesEndRef
  );

  const { openSource } = useUIStore();
  const userId = "test-user";

  const [inputBoxHeight, setInputBoxHeight] = useState(80);

  /* 👇 스트림 상태(에페메랄) */
  const [streaming, setStreaming] = useState(false);
  const [streamPrep, setStreamPrep] = useState<string | null>(null);
  // ❗ any 제거: 명시적 Source 타입 사용
  const [streamSources, setStreamSources] = useState<Source[] | null>(null);
  const [streamText, setStreamText] = useState("");
  const streamTextRef = useRef("");
  const streamAbortRef = useRef<{ abort: () => void } | null>(null);
  const streamFinalizedRef = useRef(false);

  // 전송
  const handleSend = async () => {
    if (!draft.trim() || !conversationId) return;

    const userText = draft.trim();
    setDraft(conversationId, "");

    if (!USE_STREAMING) {
      // 기존 논-스트림 경로(스토어 내부 askBot 사용)
      await sendMessage(conversationId, userId, userText);
      scrollToBottom();
      return;
    }

    try {
      setStreaming(true);
      setStreamPrep(null);
      setStreamSources(null);
      setStreamText("");
      streamTextRef.current = "";
      streamFinalizedRef.current = false;

      // 사용자 메시지는 DB 저장(완성본만 저장 원칙에서 'assistant'만 저장해도 되지만,
      // 보통 user도 저장합니다. 필요 없으면 이 줄 삭제 가능)
      addMessage({ role: "user", content: userText });
      await saveMessage(conversationId, userId, "user", userText);

      streamAbortRef.current = askStream(conversationId, userText, {
        onPrep: (s) => {
          setStreamPrep(s);
          scrollToBottom();
        },
        // ❗ any 사용 금지: unknown으로 받고 런타임 체크 후 캐스팅
        onSources: (xs: unknown) => {
          const arr = Array.isArray(xs) ? (xs as Source[]) : [];
          setStreamSources(arr);
          scrollToBottom();
        },
        onChunk: (delta) => {
          setStreamText((prev) => {
            const next = prev + delta;
            streamTextRef.current = next;
            return next;
          });
          scrollToBottom();
        },
        // ❗ 'meta' 미사용 경고 제거: 파라미터 삭제 (또는 _meta 로 변경)
        onDone: async (meta) => {
          if (streamFinalizedRef.current) return;

          // partial(중단/에러) 응답은 저장하지 않음
          if (meta?.partial) {
            setStreaming(false);
            return;
          }

          streamFinalizedRef.current = true;
          setStreaming(false);

          const finalText = streamTextRef.current.trim();
          if (finalText) {
            addMessage({ role: "assistant", content: finalText });
            await saveMessage(conversationId, userId, "assistant", finalText);
          }

          setStreamText("");
          setStreamSources(null);
          setStreamPrep(null);
          scrollToBottom();
        },
        onError: (err) => {
          console.error("stream error:", err);
          setStreaming(false);
        },
      });
    } catch (e) {
      console.error(e);
      setStreaming(false);
    }
  };

  /* textarea 자동 높이 */
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [draft]);

  /* 입력창 높이 추적 */
  useEffect(() => {
    if (!textareaWrapperRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) setInputBoxHeight(entry.contentRect.height);
    });
    observer.observe(textareaWrapperRef.current);
    return () => observer.disconnect();
  }, []);

  /* 언마운트 시 스트림 중단 */
  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    streamTextRef.current = streamText;
  }, [streamText]);

  return (
    <div
      ref={containerRef}
      className="flex-1 flex flex-col max-w-[58rem] w-full bg-white relative mx-auto overflow-y-auto"
    >
      {/* 메시지 영역 */}
      <div className="flex-1 p-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-gray-500 space-y-4">
            <h2 className="text-xl font-semibold">무엇을 도와드릴까요? 🤔</h2>
            <p className="text-sm">아래 예시 질문을 클릭해 대화를 시작해보세요.</p>
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
          <>
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`mb-6 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "user" ? (
                  <div className="ml-auto text-lg bg-blue-200 text-black font-semibold p-3 rounded-2xl inline-block max-w-[75%]">
                    {msg.content}
                  </div>
                ) : (
                  <div className="prose prose-lg max-w-none text-gray-800">
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
            ))}

            {/* 스트리밍 중일 때 에페메랄 프리뷰 */}
            {streaming && (
              <div className="mb-6 flex justify-start">
                <div className="prose prose-lg max-w-none text-gray-800">
                  {streamPrep && (
                    <div className="text-sm text-gray-500 mb-2">{streamPrep}</div>
                  )}
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
                    {streamText || " "}
                  </ReactMarkdown>
                  {streamSources?.length ? (
                      <div className="mt-2 text-xs text-gray-500">출처 {streamSources.length}개 로딩됨</div>
                    ) : null}
                </div>
              </div>
            )}
          </>
        )}

        {(isLoading || streaming) && (
          <span className="inline-flex items-center gap-2 text-gray-500 text-sm italic">
            응답 생성 중... <Aperture className="w-6 h-6 animate-spin" />
          </span>
        )}
        {error && <div className="text-red-500 text-sm">에러 발생: {error}</div>}

        <div ref={messagesEndRef} />
      </div>

      {/* 맨 아래 버튼 (입력창 높이 기반 위치) */}
      {showScrollButton && (
        <div className="sticky flex justify-center" style={{ bottom: inputBoxHeight + 30 }}>
          <button
            onClick={scrollToBottom}
            className="bg-blue-200 text-white p-3 rounded-full shadow-lg 
                       opacity-80 hover:opacity-100 hover:bg-blue-700 active:scale-90 transition"
          >
            <ChevronDown className="w-6 h-6 text-white" />
          </button>
        </div>
      )}

      {/* 입력창 */}
      <div ref={textareaWrapperRef} className="sticky bottom-2 w-full px-4 py-3 bg-transparent">
        <div className="w-full mx-auto flex items-end gap-2 bg-gray-200 rounded-2xl px-3 py-2 shadow-2xl">
          <textarea
            ref={textareaRef}
            rows={1}
            value={draft}
            onChange={(e) => setDraft(conversationId!, e.target.value)}
            onKeyDown={(e) => {
              if (isLoading || streaming) return;
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
                setTimeout(() => {
                  scrollToBottom();
                }, 0);
              }
            }}
            placeholder="메시지를 입력하세요..."
            disabled={isLoading || streaming}
            className="flex-1 resize-none bg-transparent text-lg focus:outline-none leading-snug py-2 ml-2"
          />

          {!draft.trim() ? (
            <div className="p-2 text-gray-400">
              <ShieldEllipsis className="w-5 h-5" />
            </div>
          ) : (
            <div
              onClick={() => {
                if (!isLoading && !streaming) {
                  handleSend();
                  setTimeout(() => {
                    scrollToBottom();
                  }, 0);
                }
              }}
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
