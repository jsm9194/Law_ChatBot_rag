import { useState } from "react"
import SidebarLeft from "../components/SidebarLeft"
import ChatArea from "../components/ChatArea"
import SidebarRight from "../components/SidebarRight"

export default function ChatPage() {
  const [isRightOpen, setRightOpen] = useState(false)
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)

  return (
    <div className="flex h-screen w-screen bg-[#343541]">
      {/* 좌측 */}
      <SidebarLeft />
      {/* 중앙 */}
      <div className="flex-1 flex flex-col">
        <ChatArea
          onOpenSource={(url) => {
            setSourceUrl(url)
            setRightOpen(true)
          }}
        />
      </div>
      {/* 우측 */}
      <SidebarRight
        isOpen={isRightOpen}
        sourceUrl={sourceUrl}
        onClose={() => setRightOpen(false)}
      />
    </div>
  )
}
