const BASE_URL = "http://localhost:8000";

export async function createConversation(userId: string) {
  const res = await fetch(`${BASE_URL}/conversation/new`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  return res.json();
}

export async function getConversations(userId: string) {
  const res = await fetch(`${BASE_URL}/conversations/${userId}`);
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