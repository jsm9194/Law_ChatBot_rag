// ================================
// 🌐 API BASE CONFIG
// ================================
export const BASE_URL = "http://localhost:8000";

// ================================
// 📌 기본 REST API
// ================================
export async function createConversation(userId: string) {
  const res = await fetch(`${BASE_URL}/conversation/new`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  return res.json();
}

export async function getConversations(userId: string) {
  const res = await fetch(`${BASE_URL}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!res.ok) throw new Error(`Failed to get conversations: ${res.status}`);
  return res.json();
}

export async function getConversationLogs(convId: string, limit = 10, offset = 0) {
  const res = await fetch(`${BASE_URL}/conversation/${convId}?limit=${limit}&offset=${offset}`);
  return res.json();
}

export async function askBot(conversationId: string, question: string) {
  const res = await fetch(`${BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, question }),
  });
  return res.json();
}

export async function saveMessage(
  conversationId: string,
  userId: string,
  role: string,
  content: string
) {
  const res = await fetch(`${BASE_URL}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId,
      user_id: userId,
      role,
      content,
    }),
  });
  return res.json();
}

export async function updateConversation(conversationId: string, title: string) {
  const res = await fetch(`${BASE_URL}/conversation/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  return res.json();
}

export async function deleteConversation(conversationId: string) {
  const res = await fetch(`${BASE_URL}/conversation/${conversationId}`, { method: "DELETE" });
  return res.json();
}

// ================================
// ⚡️ 스트리밍 SSE 설정 (OpenAI 표준)
// ================================

// 출처 정보 (법령·판례·뉴스 등)
export type Source = {
  law?: string;
  article?: string;
  url?: string;
  [key: string]: unknown;
};

// done 이벤트 메타정보
export type DoneMeta = {
  choices?: { finish_reason?: string }[];
  [key: string]: unknown;
};

// 스트리밍 핸들러
export type AskStreamHandlers = {
  onPrep?: (s: string) => void;
  onSources?: (xs: Source[]) => void;
  onChunk?: (delta: string) => void;
  onDone?: (meta?: DoneMeta) => void;
  onError?: (err: string) => void;
};

// Abort 예외 감지
function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === "AbortError";
}

/**
 * GPT 표준 JSON 기반 SSE 스트림 핸들러
 * 백엔드가 {"delta":{"content":"..."}} 형식으로 전송한다고 가정
 */
export function askStream(
  conversationId: string,
  question: string,
  handlers: AskStreamHandlers = {},
  debug = true
): { abort: () => void } {
  const ctrl = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${BASE_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ conversation_id: conversationId, question }),
        signal: ctrl.signal,
      });

      if (debug)
        console.log("[SSE] status", res.status, res.headers.get("content-type"));
      if (!res.ok || !res.body) {
        handlers.onError?.(`HTTP ${res.status}`);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let sawDone = false;
      let nChunk = 0;

      const mark = (label: string) => {
        if (debug) console.log(`[SSE] ${label} t=${Date.now()}ms`);
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let idx = buffer.indexOf("\n\n");

        while (idx >= 0) {
          const raw = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 2);

          if (raw) {
            const lines = raw.split("\n");
            let ev = "message";
            const dataChunks: string[] = [];

            for (const line of lines) {
              if (line.startsWith("event:")) {
                ev = line.slice(6).trim();
              } else if (line.startsWith("data:")) {
                const chunk = line.slice(5);
                dataChunks.push(chunk.startsWith(" ") ? chunk.slice(1) : chunk);
              }
            }

            const dataText = dataChunks.join("\n");

            // ===============================
            // ✅ chunk (모델 토큰 스트림)
            // ===============================
            if (ev === "chunk") {
              nChunk++;
              const parsed = JSON.parse(dataText);
              const text = parsed?.delta?.content ?? "";

              if (debug && nChunk % 20 === 0)
                console.log(`[SSE] chunk #${nChunk} (len=${text.length})`);

              if (text) handlers.onChunk?.(text);
            }

            // ===============================
            // 나머지 이벤트
            // ===============================
            else if (ev === "prep") {
              handlers.onPrep?.(dataText);
            } else if (ev === "sources") {
              try {
                const parsed = JSON.parse(dataText);
                handlers.onSources?.(Array.isArray(parsed) ? (parsed as Source[]) : []);
              } catch {
                handlers.onSources?.([]);
              }
            } else if (ev === "done") {
              sawDone = true;
              mark("done");
              const parsed = JSON.parse(dataText);
              handlers.onDone?.(parsed as DoneMeta);
            } else if (ev === "error") {
              mark("error");
              handlers.onError?.(dataText || "error");
            }
          }

          idx = buffer.indexOf("\n\n");
        }
      }

      // ✅ 스트림 종료 후 정리
      if (!sawDone) {
        console.warn("[SSE] ended without done; chunks:", nChunk);
        handlers.onDone?.({ choices: [{ finish_reason: "stream-ended" }] });
      } else {
        handlers.onDone?.({ choices: [{ finish_reason: "stop" }] });
      }
    } catch (e: unknown) {
      if (!isAbortError(e)) {
        console.error("[SSE] exception", e);
        handlers.onError?.(String(e));
      }
      handlers.onDone?.({ choices: [{ finish_reason: "exception" }] });
    }
  })();

  return { abort: () => ctrl.abort() };
}
