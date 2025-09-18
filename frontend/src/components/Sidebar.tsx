import React, { useEffect, useState } from "react";
import {
  createConversation,
  getConversations,
  updateConversation,
  deleteConversation,
} from "../api/api";

type Conversation = {
  id: string;
  title: string | null;
  created_at: string;
};

type SidebarProps = {
  onSelectConversation: (id: string) => void;
};

export default function Sidebar({ onSelectConversation }: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState<string>("");

  const userId = "test-user";

  // 대화목록 불러오기
  useEffect(() => {
    const fetchConversations = async () => {
      const data = await getConversations(userId);
      setConversations(data);
    };
    fetchConversations();
  }, []);

  // 새 대화 생성
  const handleNewConversation = async () => {
    const newConv = await createConversation(userId);
    const conv = {
      id: newConv.conversation_id,
      title: newConv.title,
      created_at: new Date().toISOString(),
    };
    setConversations((prev) => [conv, ...prev]);
    onSelectConversation(conv.id);
    setEditingId(conv.id); // 생성 후 바로 수정 모드
    setEditTitle(conv.title || "");
  };

  // 이름 변경 저장
  const handleRename = async (convId: string) => {
    if (!editTitle.trim()) {
      setEditingId(null);
      return;
    }
    const updated = await updateConversation(convId, editTitle);
    setConversations((prev) =>
      prev.map((c) => (c.id === convId ? { ...c, title: updated.title } : c))
    );
    setEditingId(null);
  };

  // 삭제
  const handleDelete = async (convId: string) => {
    if (!confirm("정말 삭제하시겠습니까?")) return;
    await deleteConversation(convId);
    setConversations((prev) => prev.filter((c) => c.id !== convId));
    setMenuOpen(null);
  };

  return (
    <div className="p-4 h-full flex flex-col">
      <h2 className="font-bold text-lg mb-4">대화목록</h2>

      <button
        className="w-full p-2 bg-blue-500 text-white rounded mb-4"
        onClick={handleNewConversation}
      >
        + 새 대화
      </button>

      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <p className="text-gray-400 text-sm">대화가 없습니다.</p>
        ) : (
          <ul className="space-y-2">
            {conversations.map((conv) => (
              <li
                key={conv.id}
                className="p-2 border rounded flex justify-between items-center hover:bg-gray-100"
              >
                {/* 제목 or input */}
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() =>
                    editingId ? null : onSelectConversation(conv.id)
                  }
                >
                  {editingId === conv.id ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onBlur={() => handleRename(conv.id)}
                      onKeyDown={(e) =>
                        e.key === "Enter" && handleRename(conv.id)
                      }
                      className="w-full border rounded px-2 py-1 text-sm"
                      autoFocus
                    />
                  ) : (
                    <>
                      <p className="font-medium">{conv.title || "제목 없음"}</p>
                      <p className="text-xs text-gray-500">
                        {new Date(conv.created_at).toLocaleString()}
                      </p>
                    </>
                  )}
                </div>

                {/* … 버튼 */}
                <div className="relative">
                  <button
                    className="px-2"
                    onClick={() =>
                      setMenuOpen(menuOpen === conv.id ? null : conv.id)
                    }
                  >
                    ⋯
                  </button>

                  {menuOpen === conv.id && (
                    <div className="absolute right-0 mt-1 w-28 bg-white border rounded shadow-md z-10">
                      <button
                        className="block w-full text-left px-3 py-2 hover:bg-gray-100"
                        onClick={() => {
                          setEditingId(conv.id);
                          setEditTitle(conv.title || "");
                          setMenuOpen(null);
                        }}
                      >
                        이름 변경
                      </button>
                      <button
                        className="block w-full text-left px-3 py-2 hover:bg-gray-100 text-red-500"
                        onClick={() => handleDelete(conv.id)}
                      >
                        삭제
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
