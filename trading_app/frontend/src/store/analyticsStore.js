import { create } from 'zustand';
import { getEquityCurve, getSymbolDistribution, getActivityFeed } from '../api/tradingApi';

export const useAnalyticsStore = create((set) => ({
  equityCurve: [],
  symbolDistribution: {},
  activityFeed: [],
  loading: false,

  setEquityCurve: (data) => set({ equityCurve: data || [] }),
  setSymbolDistribution: (data) => set({ symbolDistribution: data || {} }),
  setActivityFeed: (data) => set({ activityFeed: data || [] }),

  fetchAnalytics: async () => {
    set({ loading: true });
    try {
      const [eq, dist, act] = await Promise.all([
        getEquityCurve(),
        getSymbolDistribution(),
        getActivityFeed()
      ]);
      set({
        equityCurve: eq || [],
        symbolDistribution: dist || {},
        activityFeed: act || [],
        loading: false
      });
    } catch (e) {
      console.error('Failed to fetch analytics:', e);
      set({ loading: false });
    }
  }
}));
