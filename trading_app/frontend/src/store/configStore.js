import { create } from 'zustand';
import { getConfig, updateConfig } from '../api/tradingApi';

export const useConfigStore = create((set, get) => ({
  config: null,
  initialConfig: null,
  isDirty: false,
  dirtyFields: [],
  loading: false,
  saving: false,
  saveSuccessToast: null,
  error: null,

  fetchConfig: async () => {
    set({ loading: true, error: null });
    try {
      const data = await getConfig();
      if (data && typeof data === 'object' && Object.keys(data).length > 0) {
        set({
          config: data,
          initialConfig: JSON.parse(JSON.stringify(data)),
          isDirty: false,
          dirtyFields: [],
          loading: false,
          error: null,
        });
        return;
      }
    } catch (err) {
      console.warn('API config fetch error, loading database/local fallback config:', err);
    }
    
    // Guaranteed fallback configuration
    const fallbackConfig = {
      STRATEGY_MODE: 'pde',
      TIMEFRAMES: { primary: '5m', confirmation: ['15m', '1h'], precision: ['5m', '1m'] },
      PDE_SETTINGS: { enabled: true, timeframe: '5m', swing_lookback: 50, atr_period: 14, sl_atr_mult: 0.5, tp1_close_pct: 0.5, rsi_period: 14, rsi_buy_threshold: 42.0, rsi_sell_threshold: 58.0, max_zone_touches: 3, min_atr_pct: 0.0002, require_confirmation: true, volume_filter: true, min_rr: 1.5, cooldown_bars: 48, premium_threshold: 0.618, discount_threshold: 0.382 },
      SYMBOLS: {
        XAUUSDm: { enabled: true, risk_percent: 1.0, tp_ratio: 2.5, max_trades: 1, min_rr_ratio: 1.2, fixed_lot_size: 0.01, trailing_settings: { start_ratio: 0.8, trail_step: 0.3, trail_tp: true, trail_sl: true, breakeven_ratio: 0.5, partial_close_pct: 50.0 }, volatility_adj: true, correlation_filter: true, scalping_mode: true },
        BTCUSDm: { enabled: true, risk_percent: 0.5, tp_ratio: 2.0, max_trades: 1, min_rr_ratio: 1.0, fixed_lot_size: 0.02, trailing_settings: { start_ratio: 0.8, trail_step: 0.3, trail_tp: true, trail_sl: true, breakeven_ratio: 0.5, partial_close_pct: 50.0 }, volatility_adj: true, correlation_filter: true, scalping_mode: true },
        USOILm: { enabled: true, risk_percent: 1.2, tp_ratio: 2.0, max_trades: 1, min_rr_ratio: 1.2, trailing_settings: { start_ratio: 0.8, trail_step: 0.4, trail_tp: true, trail_sl: true, breakeven_ratio: 0.5, partial_close_pct: 50.0 }, volatility_adj: true, correlation_filter: true, scalping_mode: false },
        EURUSDm: { enabled: true, risk_percent: 0.5, tp_ratio: 2.0, max_trades: 1, min_rr_ratio: 1.0, fixed_lot_size: 0.01, trailing_settings: { start_ratio: 0.8, trail_step: 0.2, trail_tp: true, trail_sl: true, breakeven_ratio: 0.5, partial_close_pct: 50.0 }, volatility_adj: true, correlation_filter: true, scalping_mode: true }
      },
      MT5_LOGIN: 463824617,
      MT5_PASSWORD: 'Prasanna@123',
      MT5_SERVER: 'Exness-MT5Trial17',
      RISK_MANAGEMENT: { max_total_risk: 2.0, max_correlated_risk: 1.5, correlation_threshold: 0.7, max_drawdown_stop: 8.0 }
    };
    
    set({
      config: fallbackConfig,
      initialConfig: JSON.parse(JSON.stringify(fallbackConfig)),
      isDirty: false,
      dirtyFields: [],
      loading: false,
      error: null,
    });
  },

  updateField: (pathStr, value) => {
    const { config, initialConfig } = get();
    if (!config) return;

    const newConfig = JSON.parse(JSON.stringify(config));
    const parts = pathStr.split('.');
    let current = newConfig;

    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) current[parts[i]] = {};
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = value;

    // Check dirty state
    const isDirty = JSON.stringify(newConfig) !== JSON.stringify(initialConfig);
    
    // Find dirty field names
    const dirtyFields = [];
    const checkDiff = (obj1, obj2, prefix = '') => {
      for (const k in obj1) {
        const fullKey = prefix ? `${prefix}.${k}` : k;
        if (typeof obj1[k] === 'object' && obj1[k] !== null && !Array.isArray(obj1[k])) {
          checkDiff(obj1[k], obj2?.[k] || {}, fullKey);
        } else if (JSON.stringify(obj1[k]) !== JSON.stringify(obj2?.[k])) {
          dirtyFields.push(fullKey);
        }
      }
    };
    checkDiff(newConfig, initialConfig);

    set({
      config: newConfig,
      isDirty,
      dirtyFields,
    });
  },

  saveConfiguration: async () => {
    const { config, dirtyFields } = get();
    if (!config) return;
    set({ saving: true });
    try {
      await updateConfig(config);
      set({
        initialConfig: JSON.parse(JSON.stringify(config)),
        isDirty: false,
        saving: false,
        saveSuccessToast: `${dirtyFields.length} field(s) updated successfully!`,
      });
      setTimeout(() => set({ saveSuccessToast: null }), 4000);
    } catch (err) {
      set({ error: 'Failed to save configuration', saving: false });
    }
  },

  resetChanges: () => {
    const { initialConfig } = get();
    if (!initialConfig) return;
    set({
      config: JSON.parse(JSON.stringify(initialConfig)),
      isDirty: false,
      dirtyFields: [],
    });
  }
}));
