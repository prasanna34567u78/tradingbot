import { create } from 'zustand';

export const useLogStore = create((set) => ({
  logs: [
    { timestamp: new Date().toLocaleTimeString(), level: "INFO", message: "Terminal logging system initialized." },
    { timestamp: new Date().toLocaleTimeString(), level: "SUCCESS", message: "WebSocket log stream established." }
  ],
  levelFilter: 'ALL',
  searchQuery: '',
  autoScroll: true,
  logRetention: 500,

  appendLogs: (newLogs) => set((state) => {
    if (!Array.isArray(newLogs)) newLogs = [newLogs];
    if (!newLogs.length) return state;

    const existingKeys = new Set(state.logs.map((l) => `${l.timestamp}_${l.message}`));
    const uniqueIncoming = newLogs.filter((l) => !existingKeys.has(`${l.timestamp}_${l.message}`));
    
    if (uniqueIncoming.length === 0) return state;

    const combined = [...state.logs, ...uniqueIncoming];
    if (combined.length > state.logRetention) {
      combined.splice(0, combined.length - state.logRetention);
    }
    return { logs: combined };
  }),

  setLevelFilter: (level) => set({ levelFilter: level }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setAutoScroll: (val) => set({ autoScroll: val }),
  setLogRetention: (count) => set({ logRetention: count }),
  clearLogs: () => set({ logs: [] }),
}));
