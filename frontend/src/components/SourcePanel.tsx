import { useUIStore } from "../store/uiStore";
import { PanelRightClose, Expand } from "lucide-react";
import { toMobileUrl } from "./urlTransform/urlTransform";

export default function SourcePanel() {
  const { sourcePanelOpen, sourceUrl, toggleSourcePanel } = useUIStore();

  if (!sourcePanelOpen || !sourceUrl) {
    return (
      <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm"></div>
    );
  }

  // ✅ 변환 적용 + 디버깅 로그
  const iframeUrl = toMobileUrl(sourceUrl);
  console.log("[iframe 최종 URL]", iframeUrl);

  const isNamuWiki = sourceUrl.includes("namu.wiki");

  return (
    <div className="w-full h-full flex flex-col bg-white">
      {/* 상단 헤더 */}
      <div className="p-2 border-b flex justify-between items-center bg-gray-100">
        <PanelRightClose
          className="w-5 h-5 cursor-pointer"
          onClick={toggleSourcePanel}
        />
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded hover:bg-gray-200"
        >
          <Expand className="w-4 h-4 text-gray-700" />
        </a>
      </div>

      {/* iframe or fallback */}
      {isNamuWiki ? (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-500 gap-3">
          <div>나무위키는 보안 정책 때문에 직접 표시할 수 없습니다.</div>
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 bg-blue-600 !text-white px-3 py-1 rounded hover:bg-blue-800"
          >
            새 탭에서 열기
          </a>
        </div>
      ) : (
        <iframe
          src={iframeUrl}
          title="출처 페이지"
          className="w-full flex-1 border-0"
        />
      )}
    </div>
  );
}
