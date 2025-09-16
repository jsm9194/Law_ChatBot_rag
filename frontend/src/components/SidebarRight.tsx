interface SidebarRightProps {
  isOpen: boolean
  sourceUrl: string | null
  onClose: () => void
}

export default function SidebarRight({ isOpen, sourceUrl, onClose }: SidebarRightProps) {
  return (
    <div
      className={`fixed top-0 right-0 h-full w-[600px] bg-white shadow-lg transform transition-transform duration-300 ${
        isOpen ? "translate-x-0" : "translate-x-full"
      }`}
    >
      <div className="p-4 border-b flex justify-between items-center bg-gray-100">
        <h2 className="font-bold">출처</h2>
        <button onClick={onClose} className="text-gray-500">닫기 ✕</button>
      </div>
      {sourceUrl ? (
        <iframe src={sourceUrl} className="w-full h-full border-0" />
      ) : (
        <p className="p-4">출처가 없습니다.</p>
      )}
    </div>
  )
}
