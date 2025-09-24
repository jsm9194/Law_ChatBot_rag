import { useEffect, useRef, useState } from "react";
import { useChatStore } from "../store/chatStore";
import { useUIStore } from "../store/uiStore";
import axios from "axios";
import {
  NotebookPen,
  PanelRightClose,
  PanelRightOpen,
  SearchCheck,
} from "lucide-react";

export default function Sidebar() {
  const {
    conversations,
    loadConversations,
    loadMessages,
    createConversation,
    conversationId,
    setConversationId,
  } = useChatStore();

  const { sidebarOpen, toggleSidebar } = useUIStore();
  const userId = "test-user";

  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState<string>("");

  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.select();
    }
  }, [editingId]);

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

  // 대화 선택
  const handleSelectConversation = async (id: string) => {
    setConversationId(id); // ✅ 현재 선택 상태 갱신
    await loadMessages(id);
  };

  // 새 대화 생성
  const handleNewConversation = async () => {
    const newConv = await createConversation(userId);
    setConversationId(newConv.id); // ✅ 새 대화 생성 후 자동 선택
  };

  // 이름 바꾸기
  const handleRename = async (convId: string) => {
    const newTitle = editTitle.trim();
    if (!newTitle) {
      setEditingId(null);
      return;
    }

    try {
      await axios.patch(`http://localhost:8000/conversation/${convId}`, {
        title: newTitle,
      });

      // ✅ 로컬 상태 즉시 반영
      useChatStore.setState((state) => ({
        conversations: state.conversations.map((c) =>
          c.id === convId ? { ...c, title: newTitle } : c
        ),
      }));

      await loadConversations(userId);
    } catch (err) {
      console.error("이름 변경 실패:", err);
      alert("이름을 바꾸지 못했습니다.");
    } finally {
      setEditingId(null);
      setEditTitle("");
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
      {/* 상단: 열기/닫기 버튼 */}
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

      {/* 대화 목록 */}
      {sidebarOpen && (
        <div className="p-4 flex-1 overflow-y-auto">
          <h2 className="font-semibold mb-4 text-xl">대화 목록</h2>
          <ul className="space-y-2">
            {conversations.map((conv) => (
              <li
                key={conv.id}
                onClick={() =>
                  editingId ? null : handleSelectConversation(conv.id)
                }
                className={`p-2 border-none flex justify-between items-center group relative cursor-pointer rounded
                  ${
                    conv.id === conversationId
                      ? "bg-gray-300" // ✅ 선택된 대화 강조 (배경색)
                      : "hover:bg-gray-200"
                  }`}
              >
                {/* 제목 or 수정 input */}
                <div className="flex-1">
                  {editingId === conv.id ? (
                    <input
                      ref={inputRef}
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
                      <p className="font-semibold text-gray-900">
                        {conv.title || "제목 없음"}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(conv.created_at || "").toLocaleString("ko-KR", {
                          year: "numeric",
                          month: "2-digit",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          // second 안 넣으면 자동으로 안 나옴 ✅
                        })}
                      </p>
                    </>
                  )}
                </div>

                {/* ⋯ 메뉴 버튼 */}
                <div
                  className="px-2 hidden group-hover:block text-gray-500 hover:text-gray-700 cursor-pointer select-none"
                  role="button"
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation(); // ✅ 부모 클릭 막기
                    setMenuOpen(menuOpen === conv.id ? null : conv.id);
                  }}
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
