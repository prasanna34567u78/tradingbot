import React, { useState } from 'react';
import { useAccountStore } from '../store/accountStore';
import { getCurrencySymbol } from '../utils/formatters';
import { ChevronDown, ChevronUp, Shield, Zap, Sliders, Trash2, DollarSign } from 'lucide-react';

const symbolColors = {
  XAUUSDm: { text: 'text-amber-400', border: 'border-amber-500/40', badge: 'bg-amber-500/10 text-amber-400' },
  BTCUSDm: { text: 'text-orange-400', border: 'border-orange-500/40', badge: 'bg-orange-500/10 text-orange-400' },
  USOILm: { text: 'text-blue-400', border: 'border-blue-500/40', badge: 'bg-blue-500/10 text-blue-400' },
  EURUSDm: { text: 'text-emerald-400', border: 'border-emerald-500/40', badge: 'bg-emerald-500/10 text-emerald-400' },
};

export const SymbolCard = ({ symbol, data, onChange, onRemove }) => {
  const [expanded, setExpanded] = useState(false);
  const color = symbolColors[symbol] || { text: 'text-purple-400', border: 'border-purple-500/40', badge: 'bg-purple-500/10 text-purple-400' };

  const isEnabled = data?.enabled ?? false;
  const currency = useAccountStore((state) => state.account?.currency || 'USD');
  const currSym = getCurrencySymbol(currency);

  const handleToggleEnable = (e) => {
    e.stopPropagation();
    onChange(`SYMBOLS.${symbol}.enabled`, !isEnabled);
  };

  return (
    <div className={`bg-cardBg border rounded-2xl overflow-hidden transition-all ${isEnabled ? color.border : 'border-borderColor opacity-65'}`}>
      {/* Card Header */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="p-4 flex items-center justify-between cursor-pointer hover:bg-borderColor/30 transition"
      >
        <div className="flex items-center gap-3">
          <span className={`font-bold text-lg ${color.text}`}>{symbol}</span>
          {data?.scalping_mode && (
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
              Scalping Mode
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Master Enable Toggle */}
          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
            <span className="text-xs text-gray-400 font-medium">{isEnabled ? 'Enabled' : 'Disabled'}</span>
            <button
              onClick={handleToggleEnable}
              className={`w-10 h-5 flex items-center rounded-full p-0.5 transition ${isEnabled ? 'bg-accentGreen' : 'bg-gray-700'}`}
            >
              <div className={`bg-white w-4 h-4 rounded-full shadow transform transition ${isEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
          </div>

          {onRemove && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onRemove(symbol); }}
              className="p-1 text-gray-500 hover:text-accentRed transition"
              title="Remove Symbol from Config"
            >
              <Trash2 size={16} />
            </button>
          )}

          <button className="text-gray-400 hover:text-white">
            {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
        </div>
      </div>

      {/* Collapsible Settings Content */}
      {expanded && (
        <div className="p-4 border-t border-borderColor/60 bg-darkBg/50 space-y-5 text-xs">
          {/* Risk & Sizing */}
          <div>
            <h4 className="font-semibold text-gray-300 mb-3 flex items-center gap-1.5">
              <Shield size={14} className="text-accentBlue" /> Risk & Position Sizing (Account: {currency})
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <div className="flex justify-between items-center text-gray-400 mb-1">
                  <span>Risk per Trade:</span>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      min="0.1"
                      max="50.0"
                      step="0.1"
                      value={data?.risk_percent ?? 1.0}
                      onChange={(e) => onChange(`SYMBOLS.${symbol}.risk_percent`, Math.min(50.0, Math.max(0.1, parseFloat(e.target.value) || 0.1)))}
                      className="w-16 bg-darkBg border border-borderColor rounded px-1.5 py-0.5 text-right font-bold text-accentBlue font-mono text-xs"
                    />
                    <span className="text-white font-bold">%</span>
                  </div>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="50.0"
                  step="0.5"
                  value={data?.risk_percent || 1.0}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.risk_percent`, parseFloat(e.target.value))}
                  className="w-full accent-accentBlue"
                />
              </div>

              <div>
                <label className="block text-gray-400 mb-1">Take Profit Ratio: <span className="text-white font-semibold">{data?.tp_ratio}x</span></label>
                <input
                  type="range"
                  min="0.5"
                  max="5.0"
                  step="0.1"
                  value={data?.tp_ratio || 2.0}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.tp_ratio`, parseFloat(e.target.value))}
                  className="w-full accent-accentBlue"
                />
              </div>

              <div>
                <label className="block text-gray-400 mb-1">Min R:R Ratio: <span className="text-white font-semibold">{data?.min_rr_ratio}x</span></label>
                <input
                  type="range"
                  min="0.5"
                  max="3.0"
                  step="0.1"
                  value={data?.min_rr_ratio || 1.0}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.min_rr_ratio`, parseFloat(e.target.value))}
                  className="w-full accent-accentBlue"
                />
              </div>

              <div>
                <label className="block text-gray-400 mb-1">
                  SL Buffer beyond Swing: <span className="text-white font-semibold">{data?.sl_atr_mult ?? 1.0}x ATR</span>
                </label>
                <input
                  type="range"
                  min="0.3"
                  max="2.5"
                  step="0.1"
                  value={data?.sl_atr_mult ?? 1.0}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.sl_atr_mult`, parseFloat(e.target.value))}
                  className="w-full accent-accentRed"
                />
              </div>

              <div>
                <label className="block text-gray-400 mb-1">Max Lot Cap (Hard Ceiling)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="5.0"
                  value={data?.max_lot_size || 0.10}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.max_lot_size`, parseFloat(e.target.value) || 0.10)}
                  className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono"
                  placeholder="e.g. 0.05 or 0.10"
                />
              </div>

              <div>
                <label className="block text-gray-400 mb-1">Max Simultaneous Trades</label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={data?.max_trades || 1}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.max_trades`, parseInt(e.target.value))}
                  className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono"
                />
              </div>
            </div>

            {/* Position Sizing Controls: Fixed Lot vs Fixed Money Amount */}
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Option A: Fixed Lot Size */}
              <div className="bg-cardBg p-3 rounded-xl border border-borderColor flex flex-col justify-between space-y-2">
                <div>
                  <span className="text-gray-200 font-semibold block text-xs">Option 1: Fixed Lot Size</span>
                  <span className="text-gray-400 text-[11px]">
                    {data?.fixed_lot_size !== null && data?.fixed_lot_size !== undefined 
                      ? `Locked at ${data.fixed_lot_size} lots per trade` 
                      : `Inactive (using dynamic calculation)`}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.02"
                    disabled={data?.fixed_lot_size === null || data?.fixed_lot_size === undefined}
                    value={data?.fixed_lot_size ?? ''}
                    onChange={(e) => onChange(`SYMBOLS.${symbol}.fixed_lot_size`, parseFloat(e.target.value) || 0.01)}
                    className="w-24 bg-darkBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono disabled:opacity-40 text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => onChange(`SYMBOLS.${symbol}.fixed_lot_size`, (data?.fixed_lot_size === null || data?.fixed_lot_size === undefined) ? 0.02 : null)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${(data?.fixed_lot_size === null || data?.fixed_lot_size === undefined) ? 'bg-accentBlue text-white shadow' : 'bg-gray-700 text-gray-300'}`}
                  >
                    {(data?.fixed_lot_size === null || data?.fixed_lot_size === undefined) ? 'Lock Fixed Lots' : 'Use Dynamic'}
                  </button>
                </div>
              </div>

              {/* Option B: Max Fixed Money Risk Amount */}
              <div className="bg-cardBg p-3 rounded-xl border border-borderColor flex flex-col justify-between space-y-2">
                <div>
                  <span className="text-gray-200 font-semibold block text-xs">Option 2: Fixed Risk Amount ({currSym} {currency})</span>
                  <span className="text-gray-400 text-[11px]">
                    {data?.max_risk_amount !== null && data?.max_risk_amount !== undefined 
                      ? `Max loss capped at ${currSym}${data.max_risk_amount} per trade` 
                      : `Inactive (using ${data?.risk_percent || 1}% of balance)`}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="10"
                    placeholder={currency === 'INR' ? '500' : '50'}
                    disabled={data?.max_risk_amount === null || data?.max_risk_amount === undefined}
                    value={data?.max_risk_amount ?? ''}
                    onChange={(e) => onChange(`SYMBOLS.${symbol}.max_risk_amount`, parseFloat(e.target.value) || 0)}
                    className="w-28 bg-darkBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono disabled:opacity-40 text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => onChange(`SYMBOLS.${symbol}.max_risk_amount`, (data?.max_risk_amount === null || data?.max_risk_amount === undefined) ? (currency === 'INR' ? 500 : 50) : null)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${(data?.max_risk_amount === null || data?.max_risk_amount === undefined) ? 'bg-emerald-600 text-white shadow' : 'bg-gray-700 text-gray-300'}`}
                  >
                    {(data?.max_risk_amount === null || data?.max_risk_amount === undefined) ? `Set ${currSym} Risk` : 'Use %'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Trailing Settings */}
          {/* Trailing & Order Management */}
          {data?.trailing_settings && (
            <div className="space-y-4 pt-1">
              <h4 className="font-semibold text-gray-200 flex items-center gap-1.5 border-b border-borderColor/50 pb-2">
                <Sliders size={14} className="text-amber-400" /> Trailing & Profit Booking Strategy
              </h4>

              {/* Sliders Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-darkBg/60 p-3.5 rounded-xl border border-borderColor/60">
                <div>
                  <div className="flex justify-between text-gray-300 mb-1">
                    <span>Start Trail (% of TP):</span>
                    <span className="font-bold text-amber-400">{data.trailing_settings.start_ratio ?? 0.8}x</span>
                  </div>
                  <input
                    type="range"
                    min="0.0"
                    max="1.5"
                    step="0.05"
                    value={data.trailing_settings.start_ratio ?? 0.8}
                    onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.start_ratio`, parseFloat(e.target.value))}
                    className="w-full accent-amber-400"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-gray-300 mb-1">
                    <span>Trail Step (ATR):</span>
                    <span className="font-bold text-amber-400">{data.trailing_settings.trail_step ?? 0.3}x</span>
                  </div>
                  <input
                    type="range"
                    min="0.05"
                    max="1.0"
                    step="0.05"
                    value={data.trailing_settings.trail_step ?? 0.3}
                    onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.trail_step`, parseFloat(e.target.value))}
                    className="w-full accent-amber-400"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-gray-300 mb-1">
                    <span>Target / BE Ratio:</span>
                    <span className="font-bold text-accentBlue">{data.trailing_settings.breakeven_ratio ?? 0.5}x</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    value={data.trailing_settings.breakeven_ratio ?? 0.5}
                    onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.breakeven_ratio`, parseFloat(e.target.value))}
                    className="w-full accent-accentBlue"
                  />
                </div>
                <div>
                  <div className="flex justify-between text-gray-300 mb-1">
                    <span>Partial Close Lot:</span>
                    <span className="font-bold text-emerald-400">{data.trailing_settings.partial_close_pct ?? 50}%</span>
                  </div>
                  <input
                    type="range"
                    min="10"
                    max="90"
                    step="5"
                    value={data.trailing_settings.partial_close_pct ?? 50}
                    onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.partial_close_pct`, parseFloat(e.target.value))}
                    className="w-full accent-emerald-400"
                  />
                </div>
              </div>

              {/* Two Grouped Toggle Panels */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                {/* Panel 1: Stop Loss Management */}
                <div className="bg-darkBg/60 p-3 rounded-xl border border-borderColor/60 space-y-2">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                    🛡️ Stop Loss Controls
                  </span>
                  <div className="space-y-1.5">
                    <label className="flex items-center justify-between p-2 rounded-lg bg-cardBg/60 border border-borderColor/40 hover:border-borderColor cursor-pointer transition">
                      <span className="text-xs font-medium text-gray-300">Trail Stop Loss</span>
                      <input
                        type="checkbox"
                        checked={data.trailing_settings.trail_sl ?? true}
                        onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.trail_sl`, e.target.checked)}
                        className="rounded bg-darkBg border-borderColor text-amber-400"
                      />
                    </label>
                    <label className="flex items-center justify-between p-2 rounded-lg bg-cardBg/60 border border-borderColor/40 hover:border-borderColor cursor-pointer transition">
                      <span className="text-xs font-medium text-gray-300">Auto Breakeven (BE)</span>
                      <input
                        type="checkbox"
                        checked={data.trailing_settings.enable_breakeven ?? true}
                        onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.enable_breakeven`, e.target.checked)}
                        className="rounded bg-darkBg border-borderColor text-accentBlue"
                      />
                    </label>
                    <label className="flex items-center justify-between p-2 rounded-lg bg-cardBg/60 border border-borderColor/40 hover:border-borderColor cursor-pointer transition">
                      <span className="text-xs font-semibold text-rose-300">Static Stop Loss (Lock Initial SL)</span>
                      <input
                        type="checkbox"
                        checked={data.trailing_settings.static_sl ?? false}
                        onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.static_sl`, e.target.checked)}
                        className="rounded bg-darkBg border-borderColor text-rose-400"
                      />
                    </label>
                  </div>
                </div>

                {/* Panel 2: Take Profit & Exit Controls */}
                <div className="bg-darkBg/60 p-3 rounded-xl border border-borderColor/60 space-y-2">
                  <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider block">
                    🎯 Take Profit & Booking Controls
                  </span>
                  <div className="space-y-1.5">
                    <label className="flex items-center justify-between p-2 rounded-lg bg-cardBg/60 border border-borderColor/40 hover:border-borderColor cursor-pointer transition">
                      <span className="text-xs font-medium text-gray-300">Trail Take Profit</span>
                      <input
                        type="checkbox"
                        checked={data.trailing_settings.trail_tp ?? true}
                        onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.trail_tp`, e.target.checked)}
                        className="rounded bg-darkBg border-borderColor text-amber-400"
                      />
                    </label>
                    <label className="flex items-center justify-between p-2 rounded-lg bg-cardBg/60 border border-borderColor/40 hover:border-borderColor cursor-pointer transition">
                      <span className="text-xs font-medium text-gray-300">Partial Book ({data.trailing_settings.partial_close_pct ?? 50}%)</span>
                      <input
                        type="checkbox"
                        checked={data.trailing_settings.enable_partial_booking ?? true}
                        onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.enable_partial_booking`, e.target.checked)}
                        className="rounded bg-darkBg border-borderColor text-emerald-400"
                      />
                    </label>
                    <label className="flex items-center justify-between p-2 rounded-lg bg-cardBg/60 border border-borderColor/40 hover:border-borderColor cursor-pointer transition">
                      <span className="text-xs font-semibold text-purple-300">Book 100% Full Trade at Target</span>
                      <input
                        type="checkbox"
                        checked={data.trailing_settings.full_close_on_be ?? false}
                        onChange={(e) => onChange(`SYMBOLS.${symbol}.trailing_settings.full_close_on_be`, e.target.checked)}
                        className="rounded bg-darkBg border-borderColor text-purple-400"
                      />
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Feature Flags */}
          <div>
            <h4 className="font-semibold text-gray-300 mb-2 flex items-center gap-1.5">
              <Zap size={14} className="text-purple-400" /> Symbol Feature Flags
            </h4>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 cursor-pointer bg-cardBg p-2.5 rounded-xl border border-borderColor flex-1">
                <input
                  type="checkbox"
                  checked={data?.volatility_adj ?? true}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.volatility_adj`, e.target.checked)}
                  className="rounded bg-darkBg border-borderColor text-purple-400"
                />
                <span>Volatility Adjustment</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer bg-cardBg p-2.5 rounded-xl border border-borderColor flex-1">
                <input
                  type="checkbox"
                  checked={data?.correlation_filter ?? true}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.correlation_filter`, e.target.checked)}
                  className="rounded bg-darkBg border-borderColor text-purple-400"
                />
                <span>Correlation Filter</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer bg-cardBg p-2.5 rounded-xl border border-borderColor flex-1">
                <input
                  type="checkbox"
                  checked={data?.scalping_mode ?? false}
                  onChange={(e) => onChange(`SYMBOLS.${symbol}.scalping_mode`, e.target.checked)}
                  className="rounded bg-darkBg border-borderColor text-purple-400"
                />
                <span>Scalping Mode</span>
              </label>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
