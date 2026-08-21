import React, { useEffect, useState } from 'react';
import { useConfigStore } from '../store/configStore';
import { getMT5Symbols } from '../api/tradingApi';
import { SymbolCard } from '../components/SymbolCard';
import { Save, RotateCcw, AlertTriangle, Shield, Sliders, Clock, Radio, CheckCircle, Database, Plus, Search } from 'lucide-react';

export const Configuration = () => {
  const config = useConfigStore((state) => state.config);
  const isDirty = useConfigStore((state) => state.isDirty);
  const dirtyFields = useConfigStore((state) => state.dirtyFields);
  const loading = useConfigStore((state) => state.loading);
  const saving = useConfigStore((state) => state.saving);
  const saveSuccessToast = useConfigStore((state) => state.saveSuccessToast);
  const error = useConfigStore((state) => state.error);
  const fetchConfig = useConfigStore((state) => state.fetchConfig);
  const updateField = useConfigStore((state) => state.updateField);
  const saveConfiguration = useConfigStore((state) => state.saveConfiguration);
  const resetChanges = useConfigStore((state) => state.resetChanges);

  const [mt5Symbols, setMt5Symbols] = useState([]);
  const [selectedAddSymbol, setSelectedAddSymbol] = useState('');

  useEffect(() => {
    fetchConfig();
    getMT5Symbols().then((list) => {
      if (Array.isArray(list)) setMt5Symbols(list);
    }).catch((e) => console.error(e));
  }, []);

  if (error || (!loading && !config)) {
    return (
      <div className="p-8 max-w-lg mx-auto text-center space-y-4 bg-cardBg border border-borderColor rounded-2xl my-12 shadow-2xl">
        <AlertTriangle size={40} className="mx-auto text-amber-400" />
        <h3 className="font-bold text-white text-lg">Unable to Load Configuration</h3>
        <p className="text-xs text-gray-400 font-mono">
          {error || 'Could not fetch config from backend API server (http://localhost:8000).'}
        </p>
        <button
          onClick={fetchConfig}
          className="px-5 py-2.5 bg-accentBlue text-white rounded-xl text-xs font-bold hover:bg-blue-600 transition flex items-center gap-2 mx-auto shadow-lg"
        >
          <RotateCcw size={14} /> Retry Loading Configuration
        </button>
      </div>
    );
  }

  if (loading || !config) {
    return (
      <div className="p-16 text-center text-gray-400 flex flex-col items-center justify-center space-y-4">
        <div className="h-10 w-10 rounded-full border-3 border-accentBlue border-t-transparent animate-spin" />
        <span className="text-sm font-bold text-white tracking-wide">Loading Bot Configuration from config.py...</span>
      </div>
    );
  }

  const strategyMode = config.STRATEGY_MODE || 'mcp_enhanced';
  const symbols = config.SYMBOLS || {};

  const handleAddSymbol = (symName) => {
    if (!symName) return;
    if (symbols[symName]) return;

    const defaultSettings = {
      enabled: true,
      risk_percent: 1.0,
      tp_ratio: 2.0,
      max_trades: 1,
      min_rr_ratio: 1.0,
      fixed_lot_size: null,
      trailing_settings: {
        start_ratio: 0.8,
        trail_step: 0.2,
        trail_tp: true,
        trail_sl: true,
        breakeven_ratio: 0.5,
        partial_close_pct: 50.0,
      },
      volatility_adj: true,
      correlation_filter: true,
      scalping_mode: false,
    };

    updateField(`SYMBOLS.${symName}`, defaultSettings);
    setSelectedAddSymbol('');
  };

  const handleRemoveSymbol = (symName) => {
    const newSymbols = { ...symbols };
    delete newSymbols[symName];
    updateField('SYMBOLS', newSymbols);
  };

  return (
    <div className="space-y-8 pb-24">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="font-bold text-white text-xl">Bot Configuration Engine</h2>
            {isDirty && (
              <span className="flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/40">
                <span className="h-2 w-2 rounded-full bg-amber-400 animate-ping" />
                Unsaved Changes ({dirtyFields.length})
              </span>
            )}
          </div>
          <span className="text-xs text-gray-400">Mapped directly to config.py variable assignments</span>
        </div>

        {saveSuccessToast && (
          <div className="px-4 py-2 bg-accentGreen/20 text-accentGreen border border-accentGreen/40 rounded-xl text-xs font-bold flex items-center gap-2 animate-bounce">
            <CheckCircle size={16} /> {saveSuccessToast}
          </div>
        )}
      </div>

      {/* Section 3.5 — Strategy Selection Mode */}
      <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-3 shadow-lg">
        <h3 className="font-bold text-white text-sm flex items-center gap-2">
          <Radio size={18} className="text-accentBlue" /> Strategy Execution Mode
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {[
            { id: 'pde', label: 'PDE Strategy (New)', desc: 'Premium / Discount / Equilibrium Zones (+235.1% 5Y Backtest)' },
            { id: 'mcp_enhanced', label: 'MCP Enhanced', desc: 'MT5 orderbook depth + spread ATR + correlation risk + AI' },
            { id: 'standard_ai', label: 'Standard AI', desc: 'Multi-timeframe SMC + 14-feature RandomForest model' },
            { id: 'scalping', label: 'Scalping', desc: 'Fast 1M/5M scalping mode' },
          ].map((mode) => (
            <div
              key={mode.id}
              onClick={() => updateField('STRATEGY_MODE', mode.id)}
              className={`p-4 rounded-xl border cursor-pointer transition ${
                strategyMode === mode.id
                  ? 'bg-accentBlue/10 border-accentBlue text-white shadow-md'
                  : 'bg-darkBg border-borderColor/60 text-gray-400 hover:border-borderColor'
              }`}
            >
              <div className="font-bold text-sm text-white mb-1">{mode.label}</div>
              <div className="text-xs text-gray-400">{mode.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Section 3.6 — Primary Timeframe Selection */}
      <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-3 shadow-lg">
        <h3 className="font-bold text-white text-sm flex items-center gap-2">
          <Clock size={18} className="text-accentBlue" /> Primary Trading Timeframe
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { id: '5m', label: '5 Minutes (5M)', desc: 'High-frequency scalping (+568,272% 5Y backtest)' },
            { id: '15m', label: '15 Minutes (15M)', desc: 'Intraday scalping (+5,368% 5Y backtest)' },
            { id: '1h', label: '1 Hour (1H)', desc: 'Macro swing trading (+235% 5Y backtest)' },
            { id: '4h', label: '4 Hours (4H)', desc: 'Long-term trend confirmation' },
          ].map((tf) => {
            const currentTf = config.TIMEFRAMES?.primary || '5m';
            return (
              <div
                key={tf.id}
                onClick={() => {
                  updateField('TIMEFRAMES.primary', tf.id);
                  updateField('PDE_SETTINGS.timeframe', tf.id);
                }}
                className={`p-4 rounded-xl border cursor-pointer transition ${
                  currentTf === tf.id
                    ? 'bg-accentBlue/10 border-accentBlue text-white shadow-md'
                    : 'bg-darkBg border-borderColor/60 text-gray-400 hover:border-borderColor'
                }`}
              >
                <div className="font-bold text-sm text-white mb-1 flex items-center justify-between">
                  {tf.label}
                  {currentTf === tf.id && (
                    <span className="text-[10px] font-bold bg-accentBlue text-white px-2 py-0.5 rounded-full">ACTIVE</span>
                  )}
                </div>
                <div className="text-xs text-gray-400">{tf.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 3.2 — Symbol Configuration & Risk Setup */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-bold text-white text-sm">3.2 Symbol Configuration & Risk Setup</h3>
            <span className="text-xs text-gray-400">Default 4 core symbols + dynamic MT5 symbol picker ({mt5Symbols.length} available)</span>
          </div>

          {/* MT5 Dynamic Symbol Picker Dropdown */}
          <div className="flex items-center gap-2 bg-cardBg border border-borderColor p-1.5 rounded-xl shadow-sm">
            <Search size={14} className="text-gray-400 ml-2" />
            <select
              value={selectedAddSymbol}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedAddSymbol(val);
                if (val) handleAddSymbol(val);
              }}
              className="bg-darkBg border border-borderColor rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-accentBlue max-w-xs font-mono"
            >
              <option value="">+ Add / Select Symbol from MT5...</option>
              {mt5Symbols.map((sym) => (
                <option key={sym} value={sym} disabled={Boolean(symbols[sym])}>
                  {sym} {symbols[sym] ? '(Already Configured)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Symbol Cards Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Object.entries(symbols).map(([symbol, symbolData]) => (
            <SymbolCard
              key={symbol}
              symbol={symbol}
              data={symbolData}
              onChange={updateField}
              onRemove={['XAUUSDm', 'BTCUSDm', 'USOILm', 'EURUSDm'].includes(symbol) ? null : handleRemoveSymbol}
            />
          ))}
        </div>
      </div>

      {/* Grid of Sections 3.1 & 3.3 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Section 3.1 MT5 Connection */}
        <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-4 text-xs shadow-lg">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <Database size={16} className="text-accentBlue" /> 3.1 MT5 Broker Connection
          </h3>
          <p className="text-gray-400 italic">Credentials map to environment variables & config.py.</p>
          <div className="space-y-3">
            <div>
              <label className="block text-gray-300 font-semibold mb-1">MT5 Login</label>
              <input
                type="number"
                value={config.MT5_LOGIN || ''}
                onChange={(e) => updateField('MT5_LOGIN', parseInt(e.target.value) || 0)}
                className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>
            <div>
              <label className="block text-gray-300 font-semibold mb-1">MT5 Password</label>
              <input
                type="password"
                value={config.MT5_PASSWORD || ''}
                onChange={(e) => updateField('MT5_PASSWORD', e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white font-mono"
              />
            </div>
            <div>
              <label className="block text-gray-300 font-semibold mb-1">MT5 Server</label>
              <input
                type="text"
                value={config.MT5_SERVER || ''}
                onChange={(e) => updateField('MT5_SERVER', e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white"
              />
            </div>
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Exness Account ID</label>
              <input
                type="text"
                value={config.ACCOUNT_ID || ''}
                onChange={(e) => updateField('ACCOUNT_ID', e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white"
              />
            </div>
          </div>
        </div>

        {/* Section 3.3 Global Risk Management */}
        <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-4 text-xs shadow-lg">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <Shield size={16} className="text-accentRed" /> 3.3 Global Risk Management
          </h3>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-gray-300 mb-1">
                <span>Max Total Risk %</span>
                <span className="font-bold text-white">{config.RISK_MANAGEMENT?.max_total_risk}%</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="10.0"
                step="0.1"
                value={config.RISK_MANAGEMENT?.max_total_risk || 2.0}
                onChange={(e) => updateField('RISK_MANAGEMENT.max_total_risk', parseFloat(e.target.value))}
                className="w-full accent-accentRed"
              />
            </div>

            <div>
              <div className="flex justify-between text-gray-300 mb-1">
                <span>Max Correlated Risk %</span>
                <span className="font-bold text-white">{config.RISK_MANAGEMENT?.max_correlated_risk}%</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="5.0"
                step="0.1"
                value={config.RISK_MANAGEMENT?.max_correlated_risk || 1.5}
                onChange={(e) => updateField('RISK_MANAGEMENT.max_correlated_risk', parseFloat(e.target.value))}
                className="w-full accent-accentRed"
              />
            </div>

            <div>
              <div className="flex justify-between text-gray-300 mb-1">
                <span>Max Drawdown Stop %</span>
                <span className="font-bold text-accentRed">{config.RISK_MANAGEMENT?.max_drawdown_stop}%</span>
              </div>
              <input
                type="range"
                min="1.0"
                max="20.0"
                step="0.5"
                value={config.RISK_MANAGEMENT?.max_drawdown_stop || 8.0}
                onChange={(e) => updateField('RISK_MANAGEMENT.max_drawdown_stop', parseFloat(e.target.value))}
                className="w-full accent-accentRed"
              />
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2">
              <div>
                <label className="block text-gray-300 mb-1">Daily Loss Limit %</label>
                <input
                  type="number"
                  step="0.5"
                  value={config.RISK_MANAGEMENT?.daily_loss_limit || 3.0}
                  onChange={(e) => updateField('RISK_MANAGEMENT.daily_loss_limit', parseFloat(e.target.value))}
                  className="w-full bg-darkBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white"
                />
              </div>
              <div>
                <label className="block text-gray-300 mb-1">Consecutive Loss Limit</label>
                <input
                  type="number"
                  value={config.RISK_MANAGEMENT?.consecutive_loss_limit || 3}
                  onChange={(e) => updateField('RISK_MANAGEMENT.consecutive_loss_limit', parseInt(e.target.value))}
                  className="w-full bg-darkBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 3.7 MCP Settings */}
      {strategyMode === 'mcp_enhanced' && (
        <div className="bg-cardBg border border-purple-500/30 p-5 rounded-2xl space-y-4 text-xs shadow-lg">
          <h3 className="font-bold text-purple-400 text-sm flex items-center gap-2">
            <Radio size={16} /> 3.7 Model Context Protocol (MCP) MT5 Tool Engine
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex items-center gap-2 cursor-pointer bg-darkBg p-3 rounded-xl border border-borderColor">
              <input
                type="checkbox"
                checked={config.MCP_SETTINGS?.enable_level2_depth ?? true}
                onChange={(e) => updateField('MCP_SETTINGS.enable_level2_depth', e.target.checked)}
                className="rounded bg-cardBg border-borderColor text-purple-400"
              />
              <span>Level 2 Orderbook Depth & Imbalance Check</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer bg-darkBg p-3 rounded-xl border border-borderColor">
              <input
                type="checkbox"
                checked={config.MCP_SETTINGS?.enable_spread_protection ?? true}
                onChange={(e) => updateField('MCP_SETTINGS.enable_spread_protection', e.target.checked)}
                className="rounded bg-cardBg border-borderColor text-purple-400"
              />
              <span>Spread Protection ATR Filter</span>
            </label>
          </div>
        </div>
      )}

      {/* Section 3.8 Scheduler Intervals Timeline */}
      <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-4 text-xs shadow-lg">
        <h3 className="font-bold text-white text-sm flex items-center gap-2">
          <Clock size={16} className="text-amber-400" /> 3.8 Scheduler Execution Intervals (Seconds)
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {Object.entries(config.SCHEDULER_INTERVALS || {}).map(([key, val]) => (
            <div key={key} className="bg-darkBg p-3 rounded-xl border border-borderColor">
              <span className="block text-gray-400 uppercase text-[10px]">{key.replace('_', ' ')}</span>
              <input
                type="number"
                value={val}
                onChange={(e) => updateField(`SCHEDULER_INTERVALS.${key}`, parseInt(e.target.value) || 10)}
                className="w-full bg-cardBg border border-borderColor rounded px-2 py-1 text-white font-mono mt-1"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Sticky Save Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-cardBg/90 backdrop-blur-md border-t border-borderColor p-4 flex items-center justify-between z-40 px-8">
        <div className="flex items-center gap-3 text-xs">
          <span className={`h-3 w-3 rounded-full ${isDirty ? 'bg-amber-400 animate-pulse' : 'bg-gray-600'}`} />
          <span className="text-gray-300 font-medium">
            {isDirty ? `Modified fields: ${dirtyFields.join(', ')}` : 'All settings synchronized with config.py'}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {isDirty && (
            <button
              onClick={resetChanges}
              className="px-4 py-2 bg-darkBg hover:bg-borderColor text-gray-300 rounded-xl text-xs font-semibold flex items-center gap-1.5 border border-borderColor"
            >
              <RotateCcw size={14} /> Reset
            </button>
          )}

          <button
            onClick={saveConfiguration}
            disabled={!isDirty || saving}
            className={`px-6 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 transition shadow-lg ${
              isDirty
                ? 'bg-accentGreen hover:bg-accentGreen/90 text-darkBg cursor-pointer'
                : 'bg-gray-800 text-gray-500 cursor-not-allowed'
            }`}
          >
            <Save size={16} />
            {saving ? 'Saving to config.py...' : 'Save Configuration'}
          </button>
        </div>
      </div>
    </div>
  );
};
