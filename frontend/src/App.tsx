import React, { useState } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import SourcePanel from "./components/SourcePanel";

function App() {
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);

  return (
    <div className="flex h-screen">
      {/* 좌측 사이드바 */}
      <div className="w-64 border-r border-gray-300 bg-gray-50">
        <Sidebar onSelectConversation={setSelectedConversationId} />
      </div>

      {/* 중앙 채팅 영역 */}
      <div className="flex-1 flex flex-col">
        {selectedConversationId ? (
          <ChatWindow conversationId={selectedConversationId} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            대화를 선택하거나 새 대화를 시작하세요.
          </div>
        )}
      </div>

      {/* 우측 출처 패널 */}
      <div className="w-96 border-l border-gray-300 bg-white hidden lg:block">
        <SourcePanel />
      </div>
    </div>
  );
}

export default App;
