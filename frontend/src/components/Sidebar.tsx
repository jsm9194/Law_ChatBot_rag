import React, { useEffect, useRef, useState } from "react";
import { useChatStore } from "../store/chatStore";
import { useUIStore } from "../store/uiStore";
import axios from "axios";
import { NotebookPen, PanelRightClose, PanelRightOpen, SearchCheck } from "lucide-react"; // ✅ 아이콘 교체

export default function Sidebar() {

  const {
    conversations,
    loadConversations,
    loadMessages,
    createConversation,
    isLoading,
    error,
  } = useChatStore();

  const { sidebarOpen, toggleSidebar } = useUIStore();
  const userId = "test-user";

  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState<string>("");

  const menuRef = useRef<HTMLDivElement>(null);
  
// -------------------이름바꾸기
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.select(); // ✅ 처음 edit 모드일 때 한 번만 전체 선택
    }
  }, [editingId]);
// -------------------

  // 대화 목록 불러오기
  useEffect(() => {
    loadConversations(userId);
  }, [loadConversations]);

  // ✅ 드롭다운 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleSelectConversation = (id: string) => loadMessages(id);
  const handleNewConversation = async () => await createConversation(userId);

  const handleRename = async (convId: string) => {
  const newTitle = editTitle.trim();
    if (!newTitle) {
      setEditingId(null);
      return;
    }

    try {
      await axios.patch(`http://localhost:8000/conversation/${convId}`, {
        title: newTitle, // ✅ 백엔드에서 요구하는 필드 확인 필요
      });

      // ✅ 로컬 상태 즉시 반영 (UX 개선)
      useChatStore.setState((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === convId ? { ...c, title: newTitle } : c
        ),
      }));

      // 서버와 동기화 (보수적)
      await loadConversations(userId);
    } catch (err) {
      console.error("이름 변경 실패:", err);
      alert("이름을 바꾸지 못했습니다.");
    } finally {
      setEditingId(null);
      setEditTitle(""); // ✅ 다음번 rename 시 초기화
    }
  };

  const handleDelete = async (convId: string) => {
    if (!confirm("정말 삭제하시겠습니까?")) return;
    await axios.delete(`http://localhost:8000/conversation/${convId}`);
    await loadConversations(userId);
    setMenuOpen(null);
  };

  return (
    <div className="h-full flex flex-col border-r border-gray-300 bg-gray-50 text-gray-800">
      {/* 상단: 열기/닫기 아이콘 (위아래로 배치, 상태에 따라 하나만 보임) */}
      <div className="flex flex-col items-center p-2">
        <PanelRightOpen
          className={`w-6 h-6 cursor-pointer text-gray-600 hover:text-gray-900 ${
            sidebarOpen ? "ml-auto block" : "hidden"
          }`}
          onClick={toggleSidebar}
        />
        <PanelRightClose
          className={`w-6 h-6 cursor-pointer text-gray-600 hover:text-gray-900 ${
            sidebarOpen ? "hidden" : "block"
          }`}
          onClick={toggleSidebar}
        />
      </div>

      {/* 새 대화 버튼 */}
      <div
        className="flex items-center gap-2 p-2 cursor-pointer hover:bg-gray-200"
        onClick={handleNewConversation}
      >
        <NotebookPen className="w-5 h-5 ml-2" />
        {sidebarOpen && <span className="font-bold">새 대화</span>}
      </div>
      <div
        className="flex items-center gap-2 p-2 cursor-pointer hover:bg-gray-200"
        onClick={handleNewConversation}
      >
        <SearchCheck className="w-5 h-5 ml-2" />
        {sidebarOpen && <span className="font-bold">검색 [구현x]</span>}
      </div>

      {/* 펼침 상태일 때만 목록 표시 */}
      {sidebarOpen && (
        <div className="p-4 flex-1 overflow-y-auto">
          <h2 className="text-lg font-semibold mb-4">대화</h2>
          <ul className="space-y-2">
            {conversations.map((conv) => (
              <li
                key={conv.id}
                className="p-2 border-none flex justify-between items-center hover:bg-gray-200 group relative"
              >
                {/* 제목 or 수정 input */}
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => (editingId ? null : handleSelectConversation(conv.id))}
                >
                  {editingId === conv.id ? (
                    <input
                      ref={inputRef} // ✅ ref 연결
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onBlur={() => handleRename(conv.id)}
                      onKeyDown={(e) => e.key === "Enter" && handleRename(conv.id)}
                      className="w-full bg-transparent font-semibold border-none outline-none text-sm text-gray-900"
                      autoFocus
                      maxLength={20}
                    />
                  ) : (
                    <>
                      <p className="font-semibold text-gray-900">{conv.title || "제목 없음"}</p>
                      <p className="text-xs text-gray-500">
                        {new Date(conv.created_at || "").toLocaleString()}
                      </p>
                    </>
                  )}
                </div>

                {/* ⋯ 아이콘 */}
                <div
                  className="px-2 hidden group-hover:block text-gray-500 hover:text-gray-700 cursor-pointer select-none"
                  role="button"
                  tabIndex={0}
                  onClick={() => setMenuOpen(menuOpen === conv.id ? null : conv.id)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && setMenuOpen(menuOpen === conv.id ? null : conv.id)
                  }
                >
                  ⋯
                </div>

                {/* 드롭다운 메뉴 */}
                {menuOpen === conv.id && (
                  <div
                    ref={menuRef}
                    className="absolute top-full right-0 mt-2 w-48 bg-gray-800 text-gray-100 rounded shadow-lg z-20 py-2"
                  >
                    <button
                      className="block w-full text-left px-4 py-2 hover:bg-gray-700"
                      onClick={() => {
                        setEditingId(conv.id);
                        setEditTitle(conv.title || "");
                        setMenuOpen(null);
                      }}
                    >
                      이름 바꾸기
                    </button>
                    <button
                      className="block w-full text-left px-4 py-2 text-red-400 hover:bg-gray-700"
                      onClick={() => handleDelete(conv.id)}
                    >
                      삭제
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
