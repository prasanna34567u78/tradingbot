import { create } from 'zustand';
import { updateAccountInfo, getAccountInfo } from '../api/tradingApi';

export const useAccountStore = create((set, get) => ({
  account: {
    balance: 2000.00,
    equity: 2000.00,
    margin: 0.00,
    free_margin: 2000.00,
    profit: 0.00,
    daily_pnl: 0.00,
    override_enabled: 0
  },
  botRunning: false,
  wsConnected: false,

  setAccount: (accountData) => set({ account: accountData }),
  setBotRunning: (running) => set({ botRunning: running }),
  setWsConnected: (connected) => set({ wsConnected: connected }),

  fetchAccount: async () => {
    try {
      const data = await getAccountInfo();
      set({ account: data });
    } catch (e) {
      console.error('Failed to fetch account:', e);
    }
  },

  saveAccountEdit: async (updatedData) => {
    try {
      const res = await updateAccountInfo(updatedData);
      set({ account: res.account });
    } catch (e) {
      console.error('Failed to update account stats:', e);
      throw e;
    }
  }
}));
