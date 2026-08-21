import React, { useState } from 'react';
import { usePositionsStore } from '../store/positionsStore';
import { X, ShieldAlert, CheckCircle, AlertTriangle, Play } from 'lucide-react';

export const ManualTradeModal = ({ isOpen, onClose }) => {
  const openNewPosition = usePositionsStore((state) => state.openNewPosition);

  const [symbol, setSymbol] = useState('BTCUSDm');
  const [direction, setDirection] = useState('BUY');
  const [lots, setLots] = useState(0.01);
  const [slPips, setSlPips] = useState(20);
  const [tpPips, setTpPips] = useState(40);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  if (!isOpen) return null;

  const getPipValue = (sym, lot) => {
    const s = sym ? sym.toLowerCase() : '';
    if (s.includes('btc')) return lot * 1.0;
    if (s.includes('xau') || s.includes('gold')) return lot * 1.0;
    if (s.includes('oil')) return lot * 1.0;
    return lot * 10.0; // Forex
  };

  const pipVal = getPipValue(symbol, lots);
  const riskAmount = (slPips * pipVal).toFixed(2);
  const rewardAmount = (tpPips * pipVal).toFixed(2);
  const rrRatio = slPips > 0 ? (tpPips / slPips).toFixed(1) : '0.0';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (lots <= 0) {
      setErrorMsg('Lot size must be greater than 0');
      return;
    }

    setSubmitting(true);
    try {
      const res = await openNewPosition({
        symbol,
        direction,
        lots: parseFloat(lots),
        sl: parseFloat(slPips) || 0,
        tp: parseFloat(tpPips) || 0,
      });

      setSuccessMsg(`Successfully opened ${direction} position #${res.ticket || 'New'} on ${symbol}!`);
      setTimeout(() => {
        setSubmitting(false);
        setSuccessMsg('');
        onClose();
      }, 1200);
    } catch (err) {
      console.error('Manual trade open error:', err);
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to execute trade');
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="bg-cardBg border border-borderColor rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl space-y-0">
        {/* Header */}
        <div className="p-5 border-b border-borderColor flex items-center justify-between bg-darkBg/60">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-accentBlue/10 text-accentBlue">
              <Play size={18} />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Execute Manual Trade</h3>
              <span className="text-xs text-gray-400">Direct execution on MetaTrader 5 broker</span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white p-1">
            <X size={20} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {errorMsg && (
            <div className="p-3 bg-accentRed/10 border border-accentRed/30 text-accentRed rounded-xl flex items-center gap-2 font-medium">
              <AlertTriangle size={16} /> {errorMsg}
            </div>
          )}

          {successMsg && (
            <div className="p-3 bg-accentGreen/10 border border-accentGreen/30 text-accentGreen rounded-xl flex items-center gap-2 font-bold animate-bounce">
              <CheckCircle size={16} /> {successMsg}
            </div>
          )}

          {/* Symbol & Direction */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Target Symbol</label>
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-bold"
              >
                <option value="BTCUSDm">BTCUSDm (Bitcoin)</option>
                <option value="XAUUSDm">XAUUSDm (Gold)</option>
                <option value="USOILm">USOILm (Crude Oil)</option>
                <option value="EURUSDm">EURUSDm (Euro)</option>
              </select>
            </div>

            <div>
              <label className="block text-gray-300 font-semibold mb-1">Order Direction</label>
              <div className="grid grid-cols-2 gap-1.5 p-1 bg-darkBg rounded-xl border border-borderColor">
                <button
                  type="button"
                  onClick={() => setDirection('BUY')}
                  className={`py-1.5 rounded-lg font-bold transition ${
                    direction === 'BUY' ? 'bg-accentGreen text-darkBg shadow' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  BUY
                </button>
                <button
                  type="button"
                  onClick={() => setDirection('SELL')}
                  className={`py-1.5 rounded-lg font-bold transition ${
                    direction === 'SELL' ? 'bg-accentRed text-white shadow' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  SELL
                </button>
              </div>
            </div>
          </div>

          {/* Volume Sizing */}
          <div>
            <label className="block text-gray-300 font-semibold mb-1">Position Size (Lots)</label>
            <div className="flex gap-2">
              <input
                type="number"
                step="0.01"
                min="0.01"
                max="10.0"
                value={lots}
                onChange={(e) => setLots(e.target.value)}
                className="flex-1 bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono font-bold text-sm"
              />
              {[0.01, 0.05, 0.1, 0.5].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setLots(preset)}
                  className="px-2.5 py-1 bg-darkBg hover:bg-borderColor text-gray-300 rounded-xl font-mono text-xs border border-borderColor"
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          {/* Stop Loss & Take Profit */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Stop Loss (Pips)</label>
              <input
                type="number"
                value={slPips}
                onChange={(e) => setSlPips(e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono"
              />
            </div>
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Take Profit (Pips)</label>
              <input
                type="number"
                value={tpPips}
                onChange={(e) => setTpPips(e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono"
              />
            </div>
          </div>

          {/* Calculated Risk Calculator Banner */}
          <div className="p-3 bg-darkBg border border-borderColor rounded-xl flex items-center justify-between text-xs font-mono">
            <div>
              <span className="text-gray-400 block">Est. Risk: <span className="text-accentRed font-bold">-${riskAmount}</span></span>
              <span className="text-gray-400 block">Est. Reward: <span className="text-accentGreen font-bold">+${rewardAmount}</span></span>
            </div>
            <div className="text-right">
              <span className="text-gray-400 block">Risk:Reward Ratio</span>
              <span className="text-sm font-bold text-accentBlue">1:{rrRatio}</span>
            </div>
          </div>

          {/* Modal Actions */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 bg-darkBg hover:bg-borderColor text-gray-300 rounded-xl text-xs font-semibold border border-borderColor"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className={`px-6 py-2.5 rounded-xl text-xs font-bold transition shadow-lg flex items-center gap-2 ${
                direction === 'BUY'
                  ? 'bg-accentGreen hover:bg-emerald-600 text-darkBg'
                  : 'bg-accentRed hover:bg-red-600 text-white'
              }`}
            >
              <Play size={14} /> {submitting ? 'Executing on MT5...' : `Execute ${direction} Trade`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
