import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
  sidebarOpen: boolean;
  sourcePanelOpen: boolean;
  theme: "light" | "dark";
  toggleSidebar: () => void;
  toggleSourcePanel: () => void;
  toggleTheme: () => void;
  setResponsiveLayout: (width: number) => void; // ✅ 추가
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      sourcePanelOpen: false,
      theme: "light",

      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      toggleSourcePanel: () => set((s) => ({ sourcePanelOpen: !s.sourcePanelOpen })),
      toggleTheme: () =>
        set((s) => ({ theme: s.theme === "light" ? "dark" : "light" })),
      setResponsiveLayout: (width) => {                // ✅ 구현
        if (width < 768) {
          set({ sidebarOpen: false, sourcePanelOpen: false });
        } else {
          set({ sidebarOpen: true });
        }
      },
    }),
    { name: "ui-storage" }
  )
);

