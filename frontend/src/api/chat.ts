export async function askBackend(question: string) {
  const res = await fetch("http://localhost:8000/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history: "" }),
  })

  if (!res.ok) {
    throw new Error("백엔드 요청 실패")
  }

  const data = await res.json()
  return data.answer as string
}
