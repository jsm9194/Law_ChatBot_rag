import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
  sidebarOpen: boolean;
  sourcePanelOpen: boolean;
  theme: "light" | "dark";
  toggleSidebar: () => void;
  toggleSourcePanel: () => void;
  toggleTheme: () => void;
  setResponsiveLayout: (width: number) => void;
  setSourceUrl: (url: string | null) => void;
  openSource: (url: string) => void;
  sourceUrl: string | null;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      sourcePanelOpen: false,
      sourceUrl: null,
      theme: "light",

      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      toggleSourcePanel: () => set((s) => ({ sourcePanelOpen: !s.sourcePanelOpen })),
      setSourceUrl: (url) => set({ sourceUrl: url }),
      openSource: (url) => set({ sourcePanelOpen: true, sourceUrl: url }),
      toggleTheme: () => set((s: UIState) => ({ theme: s.theme === "light" ? "dark" : "light" })),
      setResponsiveLayout: (width: number) => {        // ✅ 구현
        if (width < 768) {
          set({ sidebarOpen: false, sourcePanelOpen: false });
        } else {
          set({ sidebarOpen: true });
        }
      }
    }),
    { name: "ui-storage" }
  )
);

