export const BASE_URL = "http://localhost:8000";

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

  if (!res.ok) {
    throw new Error(`Failed to get conversations: ${res.status}`);
  }
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
  const res = await fetch(`${BASE_URL}/conversation/${conversationId}`, {
    method: "DELETE",
  });
  return res.json();
}


/* ------------------------- */
/*      👇 스트리밍 추가      */
/* ------------------------- */

/** 서버가 내려줄 가능성이 있는 출처 타입(필요 시 확장) */
export type Source = {
  law?: string;
  article?: string;
  url?: string;
  [key: string]: unknown;
};

/** done 이벤트에 실리는 메타(서버 구현에 맞게 확장 가능) */
export type DoneMeta = {
  id?: string;
  fallback?: "non-stream" | "stream";
  partial?: boolean;
  reason?: string;
  [key: string]: unknown;
};

export type AskStreamHandlers = {
  onPrep?: (s: string) => void;
  onSources?: (xs: Source[]) => void;
  onChunk?: (delta: string) => void;
  onDone?: (meta?: DoneMeta) => void;
  onError?: (err: string) => void;
};

/** Abort 에러 판별 (any 금지) */
function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === "AbortError";
}

/**
 * SSE로 /ask 스트림을 구독합니다.
 * 반환값의 abort()로 스트림을 중단할 수 있습니다.
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
        headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
        body: JSON.stringify({ conversation_id: conversationId, question }),
        signal: ctrl.signal,
      });

      if (debug) {
        console.log("[SSE] status", res.status, res.headers.get("content-type"));
      }

      if (!res.ok || !res.body) {
        handlers.onError?.(`HTTP ${res.status}`);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let sawDone = false;
      let nChunk = 0;
      let lastChunkAt = 0;

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

            if (ev === "chunk") {
              nChunk++;
              lastChunkAt = Date.now();
              if (debug && nChunk % 20 === 0) {
                console.log(`[SSE] chunk #${nChunk} (len=${dataText.length})`);
              }
              handlers.onChunk?.(dataText);
            } else if (ev === "prep") {
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
              // 메타는 있어도 없어도 됨
              let meta: DoneMeta | undefined;
              try { meta = JSON.parse(dataText) as DoneMeta; } catch { /* ignore */ }
              handlers.onDone?.(meta);
            } else if (ev === "error") {
              mark("error");
              // error payload는 문자열일 수 있으므로 그대로 전달
              handlers.onError?.(dataText || "error");
            }
          }

          idx = buffer.indexOf("\n\n");
        }
      }

      if (!sawDone) {
        console.warn("[SSE] ended without done; chunks:", nChunk, "lastChunkAt:", lastChunkAt);
        handlers.onDone?.({ partial: true, reason: "stream-ended" });
      } else {
        // done 이벤트에서 이미 meta를 전달했을 수 있지만,
        // 여기서는 성공 종료 신호만 보강
        handlers.onDone?.({ fallback: "stream" });
      }
    } catch (e: unknown) {
      if (!isAbortError(e)) {
        console.error("[SSE] exception", e);
        handlers.onError?.(String(e));
      }
      handlers.onDone?.({ partial: true, reason: "exception" });
    }
  })();

  return { abort: () => ctrl.abort() };
}
