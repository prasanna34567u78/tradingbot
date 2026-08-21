import { create } from 'zustand';
import { getPositions, openPosition, closePosition, modifyPosition, getHistory, getPerformance } from '../api/tradingApi';

export const usePositionsStore = create((set, get) => ({
  positions: [],
  history: [],
  performance: null,
  loading: false,
  selectedPosition: null,

  setPositions: (newPositions) => set({ positions: newPositions }),

  fetchPositions: async () => {
    try {
      const data = await getPositions();
      set({ positions: data });
    } catch (err) {
      console.error('Failed to fetch positions:', err);
    }
  },

  fetchHistoryAndPerformance: async () => {
    try {
      const [hist, perf] = await Promise.all([getHistory(), getPerformance()]);
      set({ history: hist, performance: perf });
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  },

  openNewPosition: async (tradeData) => {
    try {
      const res = await openPosition(tradeData);
      get().fetchPositions();
      return res;
    } catch (err) {
      console.error('Error opening position:', err);
      throw err;
    }
  },

  closeTrade: async (ticket) => {
    try {
      await closePosition(ticket);
      get().fetchPositions();
    } catch (err) {
      console.error('Error closing position:', err);
    }
  },

  partialCloseTrade: async (ticket, volumeOrPercent) => {
    try {
      const payload = { ticket };
      if (typeof volumeOrPercent === 'object') {
        Object.assign(payload, volumeOrPercent);
      } else if (volumeOrPercent > 0 && volumeOrPercent <= 1.0) {
        payload.volume = volumeOrPercent;
      } else if (volumeOrPercent > 1.0) {
        payload.percent = volumeOrPercent;
      } else {
        payload.percent = 50.0;
      }
      const res = await partialClosePosition(payload);
      get().fetchPositions();
      return res;
    } catch (err) {
      console.error('Error partially closing position:', err);
      throw err;
    }
  },

  modifyTrade: async (modifyData) => {
    try {
      await modifyPosition(modifyData);
      get().fetchPositions();
    } catch (err) {
      console.error('Error modifying position:', err);
    }
  },

  setSelectedPosition: (pos) => set({ selectedPosition: pos }),
}));
