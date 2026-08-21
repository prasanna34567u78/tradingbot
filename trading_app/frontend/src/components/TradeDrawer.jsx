import React, { useState, useEffect } from 'react';
import { usePositionsStore } from '../store/positionsStore';
import { X, Check, Save, Scissors, DollarSign } from 'lucide-react';

export const TradeDrawer = () => {
  const selectedPosition = usePositionsStore((state) => state.selectedPosition);
  const setSelectedPosition = usePositionsStore((state) => state.setSelectedPosition);
  const modifyTrade = usePositionsStore((state) => state.modifyTrade);
  const closeTrade = usePositionsStore((state) => state.closeTrade);
  const partialCloseTrade = usePositionsStore((state) => state.partialCloseTrade);

  const [sl, setSl] = useState('');
  const [tp, setTp] = useState('');
  const [partialLots, setPartialLots] = useState('0.01');
  const [partialLoading, setPartialLoading] = useState(false);

  useEffect(() => {
    if (selectedPosition) {
      setSl(selectedPosition.sl || '');
      setTp(selectedPosition.tp || '');
      const defaultHalf = Math.max(0.01, Math.round((selectedPosition.lots * 0.5) * 100) / 100);
      setPartialLots(defaultHalf.toString());
    }
  }, [selectedPosition]);

  if (!selectedPosition) return null;

  const handleSaveModify = async () => {
    await modifyTrade({
      ticket: selectedPosition.ticket,
      sl: parseFloat(sl) || 0,
      tp: parseFloat(tp) || 0,
    });
    setSelectedPosition(null);
  };

  const handleClose = async () => {
    await closeTrade(selectedPosition.ticket);
    setSelectedPosition(null);
  };

  const handleExecutePartial = async (pct = null) => {
    setPartialLoading(true);
    try {
      if (pct !== null) {
        await partialCloseTrade(selectedPosition.ticket, { percent: pct });
      } else {
        await partialCloseTrade(selectedPosition.ticket, { volume: parseFloat(partialLots) || 0.01 });
      }
      setSelectedPosition(null);
    } catch (e) {
      alert('Partial close error: ' + (e?.response?.data?.detail || e.message));
    } finally {
      setPartialLoading(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-cardBg border-l border-borderColor shadow-2xl z-40 p-6 flex flex-col justify-between overflow-y-auto">
      <div>
        <div className="flex items-center justify-between pb-4 border-b border-borderColor">
          <div>
            <h3 className="font-bold text-white text-base">Trade Detail #{selectedPosition.ticket}</h3>
            <span className="text-xs text-gray-400">{selectedPosition.symbol} • {selectedPosition.type}</span>
          </div>
          <button onClick={() => setSelectedPosition(null)} className="p-1 text-gray-400 hover:text-white rounded">
            <X size={18} />
          </button>
        </div>

        <div className="py-5 space-y-4 text-xs">
          <div className="bg-darkBg p-3 rounded-xl border border-borderColor grid grid-cols-2 gap-3">
            <div>
              <span className="text-gray-400 block">Active Lots</span>
              <span className="font-bold text-white text-sm">{selectedPosition.lots}</span>
            </div>
            <div>
              <span className="text-gray-400 block">Open Price</span>
              <span className="font-bold text-white text-sm">{selectedPosition.open_price}</span>
            </div>
            <div>
              <span className="text-gray-400 block">Current Price</span>
              <span className="font-bold text-white text-sm">{selectedPosition.current_price?.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-gray-400 block">Floating Profit</span>
              <span className={`font-bold text-sm ${selectedPosition.profit >= 0 ? 'text-accentGreen' : 'text-accentRed'}`}>
                ${selectedPosition.profit?.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Manual Partial Booking Panel */}
          <div className="p-3.5 bg-darkBg/90 rounded-xl border border-amber-500/30 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-amber-400 flex items-center gap-1.5 text-xs">
                <Scissors size={14} /> Manual Partial Profit Booking
              </span>
              <span className="text-[10px] text-gray-400 font-mono">Dynamic lot exit</span>
            </div>

            {/* Quick Percentage Presets */}
            <div className="grid grid-cols-3 gap-2">
              {[25, 50, 75].map((pct) => (
                <button
                  key={pct}
                  onClick={() => handleExecutePartial(pct)}
                  disabled={partialLoading}
                  className="py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold rounded-lg transition text-[11px]"
                >
                  Book {pct}%
                </button>
              ))}
            </div>

            {/* Custom Partial Lot Size */}
            <div className="flex items-center gap-2 pt-1">
              <div className="flex-1">
                <label className="text-[10px] text-gray-400 block mb-0.5">Custom Lots to Close</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max={selectedPosition.lots}
                  value={partialLots}
                  onChange={(e) => setPartialLots(e.target.value)}
                  className="w-full bg-cardBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white font-mono text-xs"
                />
              </div>
              <button
                onClick={() => handleExecutePartial(null)}
                disabled={partialLoading}
                className="mt-3.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-darkBg font-bold rounded-lg text-xs transition flex items-center gap-1"
              >
                Book Lots
              </button>
            </div>
          </div>

          {/* SL / TP Modification */}
          <div>
            <label className="block text-gray-300 font-semibold mb-1">Stop Loss Price</label>
            <input
              type="number"
              step="0.01"
              value={sl}
              onChange={(e) => setSl(e.target.value)}
              className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white font-mono"
            />
          </div>

          <div>
            <label className="block text-gray-300 font-semibold mb-1">Take Profit Price</label>
            <input
              type="number"
              step="0.01"
              value={tp}
              onChange={(e) => setTp(e.target.value)}
              className="w-full bg-darkBg border border-borderColor rounded-lg px-3 py-2 text-white font-mono"
            />
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-borderColor flex gap-3">
        <button
          onClick={handleSaveModify}
          className="flex-1 py-2.5 bg-accentBlue hover:bg-blue-600 text-white font-semibold rounded-xl flex items-center justify-center gap-1.5 transition text-xs"
        >
          <Save size={14} /> Update SL/TP
        </button>
        <button
          onClick={handleClose}
          className="px-4 py-2.5 bg-accentRed/20 hover:bg-accentRed/30 text-accentRed border border-accentRed/40 font-semibold rounded-xl transition text-xs"
        >
          Close Full
        </button>
      </div>
    </div>
  );
};
