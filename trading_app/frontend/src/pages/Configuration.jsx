import React, { useEffect, useState } from 'react';
import { useConfigStore } from '../store/configStore';
import { useAccountStore } from '../store/accountStore';
import { getCurrencySymbol } from '../utils/formatters';
import { getMT5Symbols } from '../api/tradingApi';
import { SymbolCard } from '../components/SymbolCard';
import { Save, RotateCcw, AlertTriangle, Shield, Sliders, Clock, Radio, CheckCircle, Database, Plus, Search, Globe, Zap, ArrowDownCircle, Award, Sparkles } from 'lucide-react';

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

  const currency = useAccountStore((state) => state.account?.currency || 'INR');
  const currSym = getCurrencySymbol(currency);

  const [mt5Symbols, setMt5Symbols] = useState([]);
  const [selectedAddSymbol, setSelectedAddSymbol] = useState('');
  const [appliedGlobalToast, setAppliedGlobalToast] = useState(false);
  const [propFirmSize, setPropFirmSize] = useState(10000);
  const [propFirmCurrency, setPropFirmCurrency] = useState('USD');
  const [propFirmProfile, setPropFirmProfile] = useState('conservative');
  const [appliedPropFirmToast, setAppliedPropFirmToast] = useState(false);

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

  const handleApplyGlobalRiskToAllPairs = () => {
    const globalRisk = config.RISK_MANAGEMENT || {};
    const updatedSymbols = { ...symbols };

    const gRiskPct = globalRisk.global_risk_percent ?? 1.0;
    const gFixedLot = globalRisk.global_fixed_lot_size ?? null;
    const gMaxRiskAmt = globalRisk.global_max_risk_amount ?? null;
    const gMaxLot = globalRisk.global_max_lot_size ?? 0.10;

    Object.keys(updatedSymbols).forEach((sym) => {
      updatedSymbols[sym] = {
        ...updatedSymbols[sym],
        risk_percent: gRiskPct,
        fixed_lot_size: gFixedLot,
        max_risk_amount: gMaxRiskAmt,
        max_lot_size: gMaxLot,
      };
    });

    updateField('SYMBOLS', updatedSymbols);
    setAppliedGlobalToast(true);
    setTimeout(() => setAppliedGlobalToast(false), 3500);
  };

  const handleApplyPropFirmPreset = () => {
    const size = parseFloat(propFirmSize) || 10000;
    const isINR = propFirmCurrency === 'INR';
    
    // Risk percent per trade: 0.5% (Conservative) or 1.0% (Standard)
    const riskPct = propFirmProfile === 'conservative' ? 0.5 : 1.0;
    
    // Max Dollar / Rupee Risk Cap per Trade
    const riskCap = Math.round(size * (riskPct / 100));
    
    // Lot Size calculation:
    // Base standard: 0.02 lots per $10k USD (or equivalent in INR at 1 USD ~ 85 INR)
    let baseLot;
    if (isINR) {
      baseLot = Math.max(0.01, Math.round((size / 850000) * 0.02 * 100) / 100);
    } else {
      baseLot = Math.max(0.01, Math.round((size / 10000) * 0.02 * 100) / 100);
    }
    const maxLot = Math.max(0.02, Math.round(baseLot * 2.5 * 100) / 100);
    
    // 1. Set Execution Strategy to Liquidity Sweep Structure (5M)
    updateField('STRATEGY_MODE', 'sweep_structure');
    updateField('TIMEFRAMES.primary', '5m');
    
    // 2. Set Sweep Structure Session & Fine-Tuning
    updateField('SWEEP_STRUCTURE_SETTINGS.enabled', true);
    updateField('SWEEP_STRUCTURE_SETTINGS.timeframe', '5m');
    updateField('SWEEP_STRUCTURE_SETTINGS.disable_overnight', true);
    updateField('SWEEP_STRUCTURE_SETTINGS.cooldown_bars', 8);
    updateField('SWEEP_STRUCTURE_SETTINGS.sl_buffer_pts', 0.35);
    updateField('SWEEP_STRUCTURE_SETTINGS.max_sl_pts', 20.0);
    updateField('SWEEP_STRUCTURE_SETTINGS.buy_rr', 3.0);
    updateField('SWEEP_STRUCTURE_SETTINGS.sell_rr', 2.0);
    updateField('SWEEP_STRUCTURE_SETTINGS.session_filter', true);
    
    // 3. Set Master Global Risk Management (Prop Firm Rules)
    updateField('RISK_MANAGEMENT.global_risk_percent', riskPct);
    updateField('RISK_MANAGEMENT.global_max_risk_amount', riskCap);
    updateField('RISK_MANAGEMENT.global_fixed_lot_size', baseLot);
    updateField('RISK_MANAGEMENT.global_max_lot_size', maxLot);
    updateField('RISK_MANAGEMENT.max_daily_losses', 2);
    updateField('RISK_MANAGEMENT.daily_loss_limit', 4.0);
    updateField('RISK_MANAGEMENT.max_drawdown_stop', 8.0);
    updateField('RISK_MANAGEMENT.max_total_risk', 2.0);
    updateField('RISK_MANAGEMENT.max_correlated_risk', 1.5);
    updateField('RISK_MANAGEMENT.consecutive_loss_limit', 2);
    
    // 4. Update all active symbols with matching risk parameters
    const updatedSymbols = { ...symbols };
    Object.keys(updatedSymbols).forEach((sym) => {
      updatedSymbols[sym] = {
        ...updatedSymbols[sym],
        risk_percent: riskPct,
        fixed_lot_size: baseLot,
        max_risk_amount: riskCap,
        max_lot_size: maxLot,
        max_trades: 1,
      };
    });
    updateField('SYMBOLS', updatedSymbols);
    
    setAppliedPropFirmToast(true);
    setTimeout(() => setAppliedPropFirmToast(false), 6000);
  };

  const handleAddSymbol = (symName) => {
    if (!symName) return;
    if (symbols[symName]) return;

    const defaultSettings = {
      enabled: true,
      risk_percent: config.RISK_MANAGEMENT?.global_risk_percent || 1.0,
      tp_ratio: 2.0,
      max_trades: 1,
      min_rr_ratio: 1.0,
      fixed_lot_size: config.RISK_MANAGEMENT?.global_fixed_lot_size || null,
      max_risk_amount: config.RISK_MANAGEMENT?.global_max_risk_amount || null,
      max_lot_size: config.RISK_MANAGEMENT?.global_max_lot_size || 0.10,
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
          <Sliders size={16} className="text-accentBlue" /> 3.5 AI Trading Strategy Mode
        </h3>
        <p className="text-gray-400 text-xs">
          Select the active execution engine driving trading signals across all loaded symbols.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {[
            { id: 'pde', title: 'PDE (Premium / Discount Engine)', desc: 'Institutional SMC value area targeting 70% Value Area + daily sessions.' },
            { id: 'mcp_enhanced', title: 'DeepSeek MCP Enhanced', desc: 'Combines dynamic order blocks, FVG liquidity, and deep reasoning.' },
            { id: 'volume_profile', title: '⚡ Liquidity Sweep Structure (BUY 1:3 / SELL 1:2)', desc: 'Institutional SSL/BSL sweeps + 50% retest in Asian & NY power sessions. Highest 1Y profit.' },
            { id: 'scalping', title: 'High-Frequency M1 Scalping', desc: 'Precision rapid executions off microstructure orderflow breaks.' },
          ].map((mode) => {
            const isCurrent = (strategyMode === mode.id);
            return (
              <div
                key={mode.id}
                onClick={() => updateField('STRATEGY_MODE', mode.id)}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  isCurrent
                    ? 'border-accentBlue bg-accentBlue/10 shadow-md ring-1 ring-accentBlue'
                    : 'border-borderColor bg-darkBg hover:border-gray-600'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`font-bold text-xs ${isCurrent ? 'text-accentBlue' : 'text-white'}`}>
                    {mode.title}
                  </span>
                  {isCurrent && (
                    <span className="text-[10px] font-bold bg-accentBlue text-white px-2 py-0.5 rounded-full">ACTIVE</span>
                  )}
                </div>
                <div className="text-xs text-gray-400">{mode.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Section 3.6 — Primary Timeframe Selection */}
      <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-3 shadow-lg">
        <h3 className="font-bold text-white text-sm flex items-center gap-2">
          <Clock size={16} className="text-accentBlue" /> 3.6 Primary Trading Timeframe
        </h3>
        <p className="text-gray-400 text-xs">
          Select the primary candle resolution used for market structure analysis and signal execution.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-1">
          {[
            { id: '1m', label: '1 Minute (1M)', desc: 'Ultra-fast microstructure orderflow & M1 scalping' },
            { id: '5m', label: '5 Minutes (5M)', desc: 'Standard high-frequency PDE & SMC primary setup' },
            { id: '15m', label: '15 Minutes (15M)', desc: 'Intraday structural continuation & liquidity sweeps' },
            { id: '1h', label: '1 Hour (1H)', desc: 'Macro swing value area & high-timeframe trend' },
          ].map((tf) => {
            const currentTf = config.TIMEFRAMES?.primary || '5m';
            const isCurrent = (currentTf === tf.id);
            return (
              <div
                key={tf.id}
                onClick={() => {
                  updateField('TIMEFRAMES.primary', tf.id);
                  updateField('PDE_SETTINGS.timeframe', tf.id);
                }}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  isCurrent
                    ? 'border-accentBlue bg-accentBlue/10 shadow-md ring-1 ring-accentBlue'
                    : 'border-borderColor bg-darkBg hover:border-gray-600'
                }`}
              >
                <div className="font-bold text-xs text-white mb-1 flex items-center justify-between">
                  <span className={isCurrent ? 'text-accentBlue' : 'text-white'}>{tf.label}</span>
                  {isCurrent && (
                    <span className="text-[10px] font-bold bg-accentBlue text-white px-2 py-0.5 rounded-full">ACTIVE</span>
                  )}
                </div>
                <div className="text-xs text-gray-400">{tf.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 🛡️ Section 3.7 — Sweep Structure Session Window & Overnight Control */}
      <div className="bg-cardBg border border-emerald-500/40 p-5 rounded-2xl space-y-4 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-borderColor/60 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-xl border border-emerald-500/30">
              <Shield size={20} />
            </div>
            <div>
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                Sweep Structure Session Window & Overnight Filter
              </h3>
              <span className="text-xs text-gray-400">
                Configure institutional trading sessions for the Sweep Structure strategy (Asian, NY Power, Overnight)
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-300">Overnight (18:00–00:00 UTC):</span>
            <button
              type="button"
              onClick={() => {
                const currentVal = config.SWEEP_STRUCTURE_SETTINGS?.disable_overnight ?? true;
                updateField('SWEEP_STRUCTURE_SETTINGS.disable_overnight', !currentVal);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
                (config.SWEEP_STRUCTURE_SETTINGS?.disable_overnight ?? true)
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                  : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
              }`}
            >
              {(config.SWEEP_STRUCTURE_SETTINGS?.disable_overnight ?? true) ? '🛡️ Overnight DISABLED (Recommended)' : '⚠️ Overnight ENABLED'}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
          <div className={`p-4 rounded-xl border transition ${
            (config.SWEEP_STRUCTURE_SETTINGS?.disable_overnight ?? true)
              ? 'border-emerald-500/40 bg-emerald-500/10'
              : 'border-borderColor bg-darkBg'
          }`}>
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold text-xs text-white">Asian Session (00:00 – 07:00 UTC)</span>
              <span className="text-[10px] font-bold bg-emerald-500/30 text-emerald-300 px-2 py-0.5 rounded-full">ACTIVE</span>
            </div>
            <p className="text-[11px] text-gray-400">High win-rate Asian range sweeps with 06:30 entry cutoff & 07:30 auto-close.</p>
          </div>

          <div className={`p-4 rounded-xl border transition ${
            (config.SWEEP_STRUCTURE_SETTINGS?.disable_overnight ?? true)
              ? 'border-emerald-500/40 bg-emerald-500/10'
              : 'border-borderColor bg-darkBg'
          }`}>
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold text-xs text-white">NY Power Session (13:00 – 18:00 UTC)</span>
              <span className="text-[10px] font-bold bg-emerald-500/30 text-emerald-300 px-2 py-0.5 rounded-full">ACTIVE</span>
            </div>
            <p className="text-[11px] text-gray-400">High volume institutional trend extensions during US cash open overlap.</p>
          </div>

          <div className={`p-4 rounded-xl border transition ${
            !(config.SWEEP_STRUCTURE_SETTINGS?.disable_overnight ?? true)
              ? 'border-amber-500/40 bg-amber-500/10'
              : 'border-borderColor bg-darkBg opacity-60'
          }`}>
            <div className="flex items-center justify-between mb-1">
              <span className="font-bold text-xs text-white">Overnight Session (18:00 – 00:00 UTC)</span>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                (config.SWEEP_STRUCTURE_SETTINGS?.disable_overnight ?? true)
                  ? 'bg-red-500/20 text-red-400'
                  : 'bg-amber-500/30 text-amber-300'
              }`}>
                {(config.SWEEP_STRUCTURE_SETTINGS?.disable_overnight ?? true) ? 'BLOCKED' : 'ACTIVE'}
              </span>
            </div>
            <p className="text-[11px] text-gray-400">Low liquidity chop after US close. Disabling eliminates ~₹8,900 of drawdown.</p>
          </div>
        </div>

        {/* 🎛️ Fine-Tuning Controls for Sweep Structure Strategy */}
        <div className="bg-darkBg/90 border border-emerald-500/20 p-4 rounded-xl space-y-3">
          <div className="flex items-center justify-between border-b border-borderColor/40 pb-2">
            <span className="font-bold text-xs text-white flex items-center gap-1.5">
              <Shield size={14} className="text-emerald-400" /> Sweep Structure Risk & SL Fine-Tuning
            </span>
            <span className="text-[11px] text-gray-400">Institutional entry & exit boundaries</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-xs">
            <div>
              <label className="block text-gray-300 font-semibold mb-1">SL Buffer (pts)</label>
              <input
                type="number"
                step="0.05"
                min="0.10"
                max="5.0"
                value={config.SWEEP_STRUCTURE_SETTINGS?.sl_buffer_pts ?? 0.35}
                onChange={(e) => updateField('SWEEP_STRUCTURE_SETTINGS.sl_buffer_pts', parseFloat(e.target.value) || 0.35)}
                className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono"
              />
              <span className="text-[10px] text-gray-400">Pts past swing wick</span>
            </div>

            <div>
              <label className="block text-gray-300 font-semibold mb-1">Max SL Cap (pts)</label>
              <input
                type="number"
                step="1.0"
                min="2.0"
                max="50.0"
                value={config.SWEEP_STRUCTURE_SETTINGS?.max_sl_pts ?? 20.0}
                onChange={(e) => updateField('SWEEP_STRUCTURE_SETTINGS.max_sl_pts', parseFloat(e.target.value) || 20.0)}
                className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono"
              />
              <span className="text-[10px] text-gray-400">Max SL distance filter</span>
            </div>

            <div>
              <label className="block text-gray-300 font-semibold mb-1">Buy R:R Ratio</label>
              <input
                type="number"
                step="0.1"
                min="1.0"
                max="10.0"
                value={config.SWEEP_STRUCTURE_SETTINGS?.buy_rr ?? 3.0}
                onChange={(e) => updateField('SWEEP_STRUCTURE_SETTINGS.buy_rr', parseFloat(e.target.value) || 3.0)}
                className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono"
              />
              <span className="text-[10px] text-emerald-400 font-semibold">1:3 Bullish Target</span>
            </div>

            <div>
              <label className="block text-gray-300 font-semibold mb-1">Sell R:R Ratio</label>
              <input
                type="number"
                step="0.1"
                min="1.0"
                max="10.0"
                value={config.SWEEP_STRUCTURE_SETTINGS?.sell_rr ?? 2.0}
                onChange={(e) => updateField('SWEEP_STRUCTURE_SETTINGS.sell_rr', parseFloat(e.target.value) || 2.0)}
                className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono"
              />
              <span className="text-[10px] text-amber-400 font-semibold">1:2 Bearish Target</span>
            </div>

            <div>
              <label className="block text-gray-300 font-semibold mb-1">Cooldown Bars</label>
              <input
                type="number"
                min="1"
                max="50"
                value={config.SWEEP_STRUCTURE_SETTINGS?.cooldown_bars ?? 8}
                onChange={(e) => updateField('SWEEP_STRUCTURE_SETTINGS.cooldown_bars', parseInt(e.target.value) || 8)}
                className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono"
              />
              <span className="text-[10px] text-gray-400">8 bars = 40 mins</span>
            </div>
          </div>
        </div>
      </div>

      {/* 🌐 Master Global Risk Management (Across All Pairs) */}
      <div className="bg-gradient-to-r from-cardBg via-cardBg to-darkBg border border-accentBlue/40 p-5 rounded-2xl space-y-4 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-borderColor/60 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-accentBlue/20 text-accentBlue rounded-xl border border-accentBlue/30">
              <Globe size={20} />
            </div>
            <div>
              <h3 className="font-bold text-white text-base flex items-center gap-2">
                Global Risk Policy Across All Pairs
              </h3>
              <span className="text-xs text-gray-400">
                Master risk parameters applied across all {Object.keys(symbols).length} symbols (Account Currency: <span className="text-white font-semibold">{currSym} {currency}</span>)
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {appliedGlobalToast && (
              <span className="text-xs font-bold text-accentGreen flex items-center gap-1 bg-accentGreen/20 px-3 py-1.5 rounded-xl border border-accentGreen/30 animate-pulse">
                <CheckCircle size={14} /> Applied to All {Object.keys(symbols).length} Pairs!
              </span>
            )}
            <button
              type="button"
              onClick={handleApplyGlobalRiskToAllPairs}
              className="px-4 py-2 bg-accentBlue hover:bg-blue-600 text-white rounded-xl text-xs font-bold transition flex items-center gap-2 shadow-lg hover:shadow-accentBlue/20 active:scale-95"
            >
              <Zap size={14} /> Apply Global Risk to All Pairs
            </button>
          </div>
        </div>

        {/* Global Controls Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 text-xs">
          {/* Global Risk % */}
          <div className="bg-darkBg/80 border border-borderColor p-3 rounded-xl space-y-2">
            <div className="flex justify-between items-center text-gray-300">
              <span className="font-semibold">Global Risk %:</span>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min="0.1"
                  max="50.0"
                  step="0.1"
                  value={config.RISK_MANAGEMENT?.global_risk_percent ?? 1.0}
                  onChange={(e) => updateField('RISK_MANAGEMENT.global_risk_percent', Math.min(50.0, Math.max(0.1, parseFloat(e.target.value) || 0.1)))}
                  className="w-16 bg-cardBg border border-borderColor rounded px-1.5 py-0.5 text-right font-bold text-accentBlue font-mono text-xs"
                />
                <span className="text-white font-bold">%</span>
              </div>
            </div>
            <input
              type="range"
              min="0.1"
              max="50.0"
              step="0.5"
              value={config.RISK_MANAGEMENT?.global_risk_percent ?? 1.0}
              onChange={(e) => updateField('RISK_MANAGEMENT.global_risk_percent', parseFloat(e.target.value))}
              className="w-full accent-accentBlue"
            />
          </div>

          {/* Global Max Risk Amount ($ / ₹ Cap) */}
          <div className="bg-darkBg/80 border border-borderColor p-3 rounded-xl space-y-2">
            <div className="flex justify-between items-center text-gray-300">
              <span className="font-semibold">Max Risk Cap / Trade:</span>
              <span className="text-emerald-400 font-bold text-[11px]">{currSym} {currency}</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="10"
                placeholder={currency === 'INR' ? 'e.g. 2000' : 'e.g. 50'}
                value={config.RISK_MANAGEMENT?.global_max_risk_amount ?? ''}
                onChange={(e) => updateField('RISK_MANAGEMENT.global_max_risk_amount', e.target.value ? parseFloat(e.target.value) : null)}
                className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono text-xs"
              />
              <button
                type="button"
                onClick={() => updateField('RISK_MANAGEMENT.global_max_risk_amount', config.RISK_MANAGEMENT?.global_max_risk_amount ? null : (currency === 'INR' ? 2000 : 50))}
                className={`px-2.5 py-1.5 rounded-lg text-[11px] font-semibold whitespace-nowrap transition ${config.RISK_MANAGEMENT?.global_max_risk_amount ? 'bg-emerald-600 text-white' : 'bg-gray-700 text-gray-300'}`}
              >
                {config.RISK_MANAGEMENT?.global_max_risk_amount ? 'Active' : (currency === 'INR' ? '₹2000' : '$50')}
              </button>
            </div>
            <p className="text-[10px] text-gray-400">Hard limit on potential loss per trade.</p>
          </div>

          {/* Hard Daily Circuit Breaker */}
          <div className="bg-darkBg/80 border border-borderColor p-3 rounded-xl space-y-2">
            <div className="flex justify-between items-center text-gray-300">
              <span className="font-semibold">Daily Loss Limit:</span>
              <span className="text-amber-400 font-mono font-bold text-[11px]">Circuit Breaker</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="20"
                step="1"
                placeholder="e.g. 2"
                value={config.RISK_MANAGEMENT?.max_daily_losses ?? 2}
                onChange={(e) => updateField('RISK_MANAGEMENT.max_daily_losses', parseInt(e.target.value) || 2)}
                className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono text-xs"
              />
              <span className="text-gray-400 text-[11px] whitespace-nowrap">Losses</span>
            </div>
            <p className="text-[10px] text-gray-400">Halts trading until 00:00 UTC if N losses hit today.</p>
          </div>

          {/* Global Fixed Lot Size */}
          <div className="bg-darkBg/80 border border-borderColor p-3 rounded-xl space-y-2">
            <div className="flex justify-between items-center text-gray-300">
              <span className="font-semibold">Global Fixed Lot:</span>
              <span className="text-gray-400 text-[11px]">Micro-Lot</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.01"
                placeholder="e.g. 0.02"
                value={config.RISK_MANAGEMENT?.global_fixed_lot_size ?? ''}
                onChange={(e) => updateField('RISK_MANAGEMENT.global_fixed_lot_size', e.target.value ? parseFloat(e.target.value) : null)}
                className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono text-xs"
              />
              <button
                type="button"
                onClick={() => updateField('RISK_MANAGEMENT.global_fixed_lot_size', config.RISK_MANAGEMENT?.global_fixed_lot_size ? null : 0.02)}
                className={`px-2.5 py-1.5 rounded-lg text-[11px] font-semibold whitespace-nowrap transition ${config.RISK_MANAGEMENT?.global_fixed_lot_size ? 'bg-accentBlue text-white' : 'bg-gray-700 text-gray-300'}`}
              >
                {config.RISK_MANAGEMENT?.global_fixed_lot_size ? 'Locked' : 'Use %'}
              </button>
            </div>
          </div>

          {/* Global Max Lot Cap */}
          <div className="bg-darkBg/80 border border-borderColor p-3 rounded-xl space-y-2">
            <div className="flex justify-between items-center text-gray-300">
              <span className="font-semibold">Global Max Lot Cap:</span>
              <span className="text-accentRed font-mono font-bold text-[11px]">Ceiling</span>
            </div>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max="5.0"
              value={config.RISK_MANAGEMENT?.global_max_lot_size ?? 0.10}
              onChange={(e) => updateField('RISK_MANAGEMENT.global_max_lot_size', parseFloat(e.target.value) || 0.10)}
              className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono text-xs"
              placeholder="e.g. 0.10"
            />
          </div>
        </div>
      </div>

      {/* Section 3.2 — Symbol Configuration & Individual Risk Setup */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-bold text-white text-sm">3.2 Symbol Configuration & Individual Overrides</h3>
            <span className="text-xs text-gray-400">Default core symbols + dynamic MT5 symbol picker ({mt5Symbols.length} available)</span>
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

        {/* Symbol Cards List */}
        <div className="space-y-4">
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
              <div className="flex justify-between items-center text-gray-300 mb-1">
                <span>Max Total Risk (Portfolio Limit) %</span>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    min="0.5"
                    max="100.0"
                    step="0.5"
                    value={config.RISK_MANAGEMENT?.max_total_risk ?? 15.0}
                    onChange={(e) => updateField('RISK_MANAGEMENT.max_total_risk', Math.min(100.0, Math.max(0.5, parseFloat(e.target.value) || 0.5)))}
                    className="w-16 bg-darkBg border border-borderColor rounded px-1.5 py-0.5 text-right font-bold text-white font-mono text-xs"
                  />
                  <span className="font-bold text-white">%</span>
                </div>
              </div>
              <input
                type="range"
                min="0.5"
                max="100.0"
                step="0.5"
                value={config.RISK_MANAGEMENT?.max_total_risk ?? 15.0}
                onChange={(e) => updateField('RISK_MANAGEMENT.max_total_risk', parseFloat(e.target.value))}
                className="w-full accent-accentRed"
              />
            </div>

            <div>
              <div className="flex justify-between items-center text-gray-300 mb-1">
                <span>Max Correlated Risk %</span>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    min="0.5"
                    max="50.0"
                    step="0.5"
                    value={config.RISK_MANAGEMENT?.max_correlated_risk ?? 5.0}
                    onChange={(e) => updateField('RISK_MANAGEMENT.max_correlated_risk', Math.min(50.0, Math.max(0.5, parseFloat(e.target.value) || 0.5)))}
                    className="w-16 bg-darkBg border border-borderColor rounded px-1.5 py-0.5 text-right font-bold text-white font-mono text-xs"
                  />
                  <span className="font-bold text-white">%</span>
                </div>
              </div>
              <input
                type="range"
                min="0.5"
                max="50.0"
                step="0.5"
                value={config.RISK_MANAGEMENT?.max_correlated_risk ?? 5.0}
                onChange={(e) => updateField('RISK_MANAGEMENT.max_correlated_risk', parseFloat(e.target.value))}
                className="w-full accent-accentRed"
              />
            </div>

            <div>
              <div className="flex justify-between items-center text-gray-300 mb-1">
                <span>Max Drawdown Stop %</span>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    min="1.0"
                    max="50.0"
                    step="0.5"
                    value={config.RISK_MANAGEMENT?.max_drawdown_stop ?? 15.0}
                    onChange={(e) => updateField('RISK_MANAGEMENT.max_drawdown_stop', Math.min(50.0, Math.max(1.0, parseFloat(e.target.value) || 1.0)))}
                    className="w-16 bg-darkBg border border-borderColor rounded px-1.5 py-0.5 text-right font-bold text-accentRed font-mono text-xs"
                  />
                  <span className="font-bold text-accentRed">%</span>
                </div>
              </div>
              <input
                type="range"
                min="1.0"
                max="50.0"
                step="0.5"
                value={config.RISK_MANAGEMENT?.max_drawdown_stop ?? 15.0}
                onChange={(e) => updateField('RISK_MANAGEMENT.max_drawdown_stop', parseFloat(e.target.value))}
                className="w-full accent-accentRed"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
              <div>
                <label className="block text-gray-300 mb-1">Daily Loss Limit %</label>
                <input
                  type="number"
                  step="0.5"
                  value={config.RISK_MANAGEMENT?.daily_loss_limit || 4.0}
                  onChange={(e) => updateField('RISK_MANAGEMENT.daily_loss_limit', parseFloat(e.target.value))}
                  className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white font-mono"
                />
              </div>
              <div>
                <label className="block text-gray-300 mb-1">Consecutive Loss Limit</label>
                <input
                  type="number"
                  value={config.RISK_MANAGEMENT?.consecutive_loss_limit || 3}
                  onChange={(e) => updateField('RISK_MANAGEMENT.consecutive_loss_limit', parseInt(e.target.value))}
                  className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white font-mono"
                />
              </div>
              <div>
                <label className="block text-gray-300 mb-1">Max Daily Losses (Breaker)</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={config.RISK_MANAGEMENT?.max_daily_losses ?? 2}
                  onChange={(e) => updateField('RISK_MANAGEMENT.max_daily_losses', parseInt(e.target.value) || 2)}
                  className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white font-mono"
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

      {/* 🏛️ Section 3.9 — Prop Firm Account Auto-Configurator (Downside Preset Wizard) */}
      <div className="bg-gradient-to-r from-cardBg via-darkBg to-indigo-950/40 border border-indigo-500/40 p-6 rounded-2xl space-y-5 shadow-2xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-borderColor/60 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-500/20 text-indigo-400 rounded-xl border border-indigo-500/30">
              <Award size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-white text-base">
                  3.9 Prop Firm Auto-Configuration Wizard
                </h3>
                <span className="text-[10px] font-bold bg-indigo-500/30 text-indigo-300 border border-indigo-500/40 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Sparkles size={10} /> One-Click Default Setup
                </span>
              </div>
              <span className="text-xs text-gray-400">
                Input your evaluation account size to automatically calibrate compliant risk, lot sizing, and circuit breakers (FTMO, FundedNext, Funding Pips, TopStep).
              </span>
            </div>
          </div>

          {appliedPropFirmToast && (
            <span className="text-xs font-bold text-accentGreen flex items-center gap-1.5 bg-accentGreen/20 px-3.5 py-2 rounded-xl border border-accentGreen/40 animate-pulse">
              <CheckCircle size={15} /> Prop Firm Defaults Applied! Click "Save Configuration" Below.
            </span>
          )}
        </div>

        {/* Configuration Inputs Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          {/* 1. Account Size & Currency */}
          <div className="bg-darkBg/90 border border-borderColor p-4 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-gray-300 font-bold">1. Account Size</label>
              <div className="flex items-center gap-1 bg-cardBg border border-borderColor rounded-lg p-0.5">
                {['USD', 'EUR', 'INR'].map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => {
                      setPropFirmCurrency(c);
                      if (c === 'INR' && propFirmSize < 50000) setPropFirmSize(500000);
                      if (c !== 'INR' && propFirmSize >= 50000) setPropFirmSize(10000);
                    }}
                    className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                      propFirmCurrency === c ? 'bg-indigo-600 text-white shadow' : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {c === 'USD' ? '$ USD' : (c === 'INR' ? '₹ INR' : '€ EUR')}
                  </button>
                ))}
              </div>
            </div>

            <div className="relative">
              <span className="absolute left-3 top-2.5 text-gray-400 font-bold font-mono">
                {propFirmCurrency === 'INR' ? '₹' : (propFirmCurrency === 'EUR' ? '€' : '$')}
              </span>
              <input
                type="number"
                step={propFirmCurrency === 'INR' ? 50000 : 5000}
                value={propFirmSize}
                onChange={(e) => setPropFirmSize(Math.max(100, parseFloat(e.target.value) || 0))}
                className="w-full bg-cardBg border border-borderColor rounded-xl pl-8 pr-3 py-2 text-white font-mono font-bold text-sm"
                placeholder="e.g. 10000"
              />
            </div>

            {/* Quick Presets */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              {(propFirmCurrency === 'INR' ? [100000, 250000, 500000, 1000000, 2500000] : [5000, 10000, 25000, 50000, 100000, 200000]).map((amt) => (
                <button
                  key={amt}
                  type="button"
                  onClick={() => setPropFirmSize(amt)}
                  className={`px-2 py-1 rounded-lg text-[10px] font-mono font-semibold transition ${
                    propFirmSize === amt
                      ? 'bg-indigo-600 text-white border border-indigo-400'
                      : 'bg-cardBg hover:bg-borderColor text-gray-300 border border-borderColor/60'
                  }`}
                >
                  {propFirmCurrency === 'INR' ? `₹${amt / 1000}k` : `$${amt / 1000}k`}
                </button>
              ))}
            </div>
          </div>

          {/* 2. Risk Profile & Strategy Mode */}
          <div className="bg-darkBg/90 border border-borderColor p-4 rounded-xl space-y-3">
            <label className="text-gray-300 font-bold block">2. Risk Profile</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setPropFirmProfile('conservative')}
                className={`p-2.5 rounded-xl border text-left transition ${
                  propFirmProfile === 'conservative'
                    ? 'border-indigo-500 bg-indigo-500/20 text-white shadow-md'
                    : 'border-borderColor bg-cardBg text-gray-400 hover:text-white'
                }`}
              >
                <div className="font-bold text-xs text-indigo-300 flex items-center justify-between">
                  <span>Conservative</span>
                  <span className="text-[10px] font-mono">0.5%</span>
                </div>
                <p className="text-[10px] text-gray-400 mt-1">Recommended for Phase 1 & 2 Evaluations.</p>
              </button>

              <button
                type="button"
                onClick={() => setPropFirmProfile('moderate')}
                className={`p-2.5 rounded-xl border text-left transition ${
                  propFirmProfile === 'moderate'
                    ? 'border-amber-500 bg-amber-500/20 text-white shadow-md'
                    : 'border-borderColor bg-cardBg text-gray-400 hover:text-white'
                }`}
              >
                <div className="font-bold text-xs text-amber-300 flex items-center justify-between">
                  <span>Standard</span>
                  <span className="text-[10px] font-mono">1.0%</span>
                </div>
                <p className="text-[10px] text-gray-400 mt-1">For funded accounts & faster scaling.</p>
              </button>
            </div>

            <div className="p-2 rounded-lg bg-cardBg border border-borderColor/60 text-[11px] text-gray-400 flex items-center justify-between">
              <span>Strategy Engine:</span>
              <span className="text-emerald-400 font-bold">Sweep Structure (5M)</span>
            </div>
          </div>

          {/* 3. Action Button */}
          <div className="bg-darkBg/90 border border-borderColor p-4 rounded-xl flex flex-col justify-between space-y-3">
            <div>
              <span className="text-gray-300 font-bold block mb-1">3. Apply & Calibrate</span>
              <p className="text-[11px] text-gray-400">
                Calibrates lot sizes, dollar SL caps, circuit breakers, and disables overnight session across all pairs.
              </p>
            </div>

            <button
              type="button"
              onClick={handleApplyPropFirmPreset}
              className="w-full py-3 bg-gradient-to-r from-indigo-600 via-indigo-500 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 active:scale-95 transition"
            >
              <Zap size={16} /> Apply Prop Firm Defaults
            </button>
          </div>
        </div>

        {/* Live Calculation Preview Banner */}
        <div className="bg-darkBg/60 border border-indigo-500/20 p-4 rounded-xl">
          <div className="flex items-center justify-between text-[11px] font-bold text-indigo-300 mb-2">
            <span>CALCULATED PARAMETERS PREVIEW FOR {propFirmCurrency === 'INR' ? '₹' : (propFirmCurrency === 'EUR' ? '€' : '$')}{propFirmSize.toLocaleString()} ACCOUNT:</span>
            <span className="text-gray-400">{propFirmProfile === 'conservative' ? 'Conservative Mode (0.5%)' : 'Standard Mode (1.0%)'}</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-xs">
            <div className="bg-cardBg p-2.5 rounded-lg border border-borderColor">
              <span className="text-[10px] text-gray-400 block">Max Risk / Trade</span>
              <span className="font-mono font-bold text-emerald-400">
                {propFirmCurrency === 'INR' ? '₹' : (propFirmCurrency === 'EUR' ? '€' : '$')}
                {Math.round(propFirmSize * ((propFirmProfile === 'conservative' ? 0.5 : 1.0) / 100)).toLocaleString()}
              </span>
              <span className="text-[9px] text-gray-500 block">({propFirmProfile === 'conservative' ? '0.5%' : '1.0%'} capital)</span>
            </div>

            <div className="bg-cardBg p-2.5 rounded-lg border border-borderColor">
              <span className="text-[10px] text-gray-400 block">Micro Lot Size</span>
              <span className="font-mono font-bold text-white">
                {propFirmCurrency === 'INR'
                  ? Math.max(0.01, Math.round((propFirmSize / 850000) * 0.02 * 100) / 100)
                  : Math.max(0.01, Math.round((propFirmSize / 10000) * 0.02 * 100) / 100)} Lots
              </span>
              <span className="text-[9px] text-gray-500 block">Safe position size</span>
            </div>

            <div className="bg-cardBg p-2.5 rounded-lg border border-borderColor">
              <span className="text-[10px] text-gray-400 block">Daily Circuit Breaker</span>
              <span className="font-mono font-bold text-amber-400">2 Losses Max</span>
              <span className="text-[9px] text-gray-500 block">Auto-halts until 00:00 UTC</span>
            </div>

            <div className="bg-cardBg p-2.5 rounded-lg border border-borderColor">
              <span className="text-[10px] text-gray-400 block">Max Daily Loss</span>
              <span className="font-mono font-bold text-amber-400">
                {propFirmProfile === 'conservative' ? '1.0% (Max 4.0%)' : '2.0% (Max 4.0%)'}
              </span>
              <span className="text-[9px] text-gray-500 block">5.0% prop firm limit safe</span>
            </div>

            <div className="bg-cardBg p-2.5 rounded-lg border border-borderColor">
              <span className="text-[10px] text-gray-400 block">Max Drawdown Stop</span>
              <span className="font-mono font-bold text-accentRed">8.0% Ceiling</span>
              <span className="text-[9px] text-gray-500 block">2% safety margin from 10%</span>
            </div>

            <div className="bg-cardBg p-2.5 rounded-lg border border-borderColor">
              <span className="text-[10px] text-gray-400 block">Overnight Session</span>
              <span className="font-mono font-bold text-emerald-400">BLOCKED</span>
              <span className="text-[9px] text-gray-500 block">18:00–00:00 UTC disabled</span>
            </div>
          </div>
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
