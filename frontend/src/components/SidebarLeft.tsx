export default function SidebarLeft() {
  return (
    <div className="w-64 bg-[#202123] text-gray-200 flex flex-col">
      {/* 상단 */}
      <div className="p-3">
        <button className="w-full py-2 px-3 bg-[#343541] hover:bg-[#40414f] rounded-md text-left">
          + 새 채팅
        </button>
      </div>

      {/* 채팅 기록 */}
      <div className="flex-1 overflow-y-auto space-y-1">
        <button className="w-full text-left px-4 py-2 hover:bg-[#2a2b32] rounded">채팅 1</button>
        <button className="w-full text-left px-4 py-2 hover:bg-[#2a2b32] rounded">채팅 2</button>
      </div>

      {/* 하단 */}
      <div className="p-3 border-t border-gray-700">
        <button className="w-full text-left px-3 py-2 hover:bg-[#2a2b32] rounded">
          ⚙ 설정
        </button>
      </div>
    </div>
  )
}
