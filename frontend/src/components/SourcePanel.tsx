import { useUIStore } from "../store/uiStore";
import { PanelRightClose, Expand } from "lucide-react"; // ✅ 아이콘 교체

export default function SourcePanel() {
  const { sourcePanelOpen, sourceUrl, toggleSourcePanel } = useUIStore();

  if (!sourcePanelOpen || !sourceUrl) {
    return (
      <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm">

      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col bg-white">
      {/* ✅ 상단 헤더 */}
      <div className="p-2 border-b flex justify-between items-center bg-gray-100">
        <PanelRightClose className="w-5 h-5 cursor-pointer" onClick={toggleSourcePanel}/>
        {/* 새 탭에서 열기 버튼 */}
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 bg-gray-100"
        >
          <Expand className="w-4 h-4 text-gray-700" />
        </a>
      </div>

      {/* ✅ iframe 영역 */}
      <iframe
        src={sourceUrl}
        title="출처 페이지"
        className="w-full flex-1 border-0"
      />
    </div>
  );
}
