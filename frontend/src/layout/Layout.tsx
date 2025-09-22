// src/layout/Layout.tsx
import React, { useEffect } from "react";
import Sidebar from "../components/Sidebar";
import ChatArea from "../components/ChatArea";
import SourcePanel from "../components/SourcePanel";
import { useChatStore } from "../store/chatStore";
import { useUIStore } from "../store/uiStore";
import { motion } from "framer-motion";

export default function Layout() {
  const { conversationId } = useChatStore();
  const { sidebarOpen, sourcePanelOpen, setResponsiveLayout } = useUIStore();

  // ✅ 반응형 대응 (화면 크기 따라 자동 열림/닫힘)
  useEffect(() => {
    const handleResize = () => {
      setResponsiveLayout(window.innerWidth);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [setResponsiveLayout]);


  return (
    <div className="w-full h-screen flex bg-white">
      {/* 좌측 사이드바 */}
      <motion.div
        animate={{ width: sidebarOpen ? 256 : 48 }}
        transition={{ duration: 0.3 }}
        className="border-r border-gray-300 bg-gray-50 max-w-[15rem]"
      >
        <Sidebar />
      </motion.div>

      {/* 중앙 채팅 영역 (전체 차지) */}
      <div className="flex-1 flex flex-col">
        {conversationId ? (
          <ChatArea />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            대화를 선택하거나 새 대화를 시작하세요.
          </div>
        )}
      </div>

      {/* 우측 출처 패널 */}
      <motion.div
        animate={{ width: sourcePanelOpen ? 384 : 48 }}
        transition={{ duration: 0.3 }}
        className="border-l border-gray-300 bg-white hidden lg:block"
      >
        <SourcePanel />
      </motion.div>
    </div>
  );
}
