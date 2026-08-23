import React from 'react';
import { usePositionsStore } from '../store/positionsStore';
import { Edit2, XCircle, TrendingUp, Shield, Zap } from 'lucide-react';

export const TradeTable = ({ onOpenManualTrade }) => {
  const positions = usePositionsStore((state) => state.positions);
  const closeTrade = usePositionsStore((state) => state.closeTrade);
  const partialCloseTrade = usePositionsStore((state) => state.partialCloseTrade);
  const setSelectedPosition = usePositionsStore((state) => state.setSelectedPosition);

  return (
    <div className="bg-cardBg border border-borderColor rounded-xl overflow-hidden flex flex-col h-full">
      <div className="p-3 sm:p-4 border-b border-borderColor flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-white text-sm">Open Positions</h3>
          <span className="text-[11px] text-gray-400">Live active positions stream ({positions.length})</span>
        </div>
        <button
          onClick={onOpenManualTrade}
          className="px-3 py-1.5 bg-accentBlue hover:bg-blue-600 text-white rounded-lg text-xs font-semibold transition shadow-sm"
        >
          + Manual Trade
        </button>
      </div>

      {/* Mobile Card List (md:hidden) */}
      <div className="md:hidden flex-1 overflow-y-auto p-3 space-y-3">
        {positions.length === 0 ? (
          <div className="p-8 text-center text-gray-500 italic text-xs">
            No open positions currently active.
          </div>
        ) : (
          positions.map((pos) => {
            const isBuy = pos.type === 'BUY';
            const isProfitable = (pos.profit || 0) >= 0;

            return (
              <div
                key={pos.ticket}
                onClick={() => setSelectedPosition(pos)}
                className="bg-darkBg/70 border border-borderColor/80 rounded-xl p-3.5 space-y-2.5 shadow-sm active:bg-darkBg/90 transition"
              >
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-white">{pos.symbol}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      isBuy 
                        ? 'bg-accentGreen/15 text-accentGreen border border-accentGreen/30' 
                        : 'bg-accentRed/15 text-accentRed border border-accentRed/30'
                    }`}>
                      {pos.type}
                    </span>
                    <span className="text-[11px] text-gray-400 font-mono font-semibold">{pos.lots} lots</span>
                  </div>

                  <div className={`text-sm font-bold font-mono ${isProfitable ? 'text-accentGreen' : 'text-accentRed'}`}>
                    {isProfitable ? `+$${pos.profit.toFixed(2)}` : `-$${Math.abs(pos.profit).toFixed(2)}`}
                  </div>
                </div>

                {/* Price Grid */}
                <div className="grid grid-cols-2 gap-2 text-[11px] bg-cardBg/60 p-2 rounded-lg border border-borderColor/40 font-mono">
                  <div>
                    <span className="text-gray-500 block text-[9px] uppercase font-sans">Open Price</span>
                    <span className="text-gray-200">{pos.open_price}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[9px] uppercase font-sans">Current Price</span>
                    <span className="text-white font-semibold">{pos.current_price?.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[9px] uppercase font-sans">SL</span>
                    <span className="text-gray-400">{pos.sl || 'None'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[9px] uppercase font-sans">TP</span>
                    <span className="text-gray-400">{pos.tp || 'None'}</span>
                  </div>
                </div>

                {/* Actions Row */}
                <div className="flex items-center gap-2 pt-1" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => partialCloseTrade(pos.ticket, 50.0)}
                    className="flex-1 py-1.5 bg-amber-500/15 hover:bg-amber-500/25 active:bg-amber-500/35 text-amber-400 border border-amber-500/30 rounded-lg font-bold text-xs transition text-center"
                  >
                    Book 50%
                  </button>
                  <button
                    onClick={() => setSelectedPosition(pos)}
                    className="p-1.5 bg-borderColor/60 hover:bg-borderColor text-gray-300 rounded-lg text-xs"
                    title="Modify Position"
                  >
                    <Edit2 size={15} />
                  </button>
                  <button
                    onClick={() => closeTrade(pos.ticket)}
                    className="p-1.5 bg-accentRed/15 hover:bg-accentRed/25 text-accentRed border border-accentRed/30 rounded-lg text-xs font-bold"
                    title="Close Full Trade"
                  >
                    <XCircle size={15} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Desktop Table View (hidden md:block) */}
      <div className="hidden md:block overflow-x-auto flex-1">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-darkBg/60 text-gray-400 border-b border-borderColor uppercase font-mono">
              <th className="p-3">Ticket</th>
              <th className="p-3">Symbol</th>
              <th className="p-3">Type</th>
              <th className="p-3">Lots</th>
              <th className="p-3">Open Price</th>
              <th className="p-3">Current</th>
              <th className="p-3">SL</th>
              <th className="p-3">TP</th>
              <th className="p-3">Profit ($)</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-borderColor/60">
            {positions.length === 0 ? (
              <tr>
                <td colSpan="10" className="p-8 text-center text-gray-500 italic">
                  No open positions currently active.
                </td>
              </tr>
            ) : (
              positions.map((pos) => (
                <tr
                  key={pos.ticket}
                  onClick={() => setSelectedPosition(pos)}
                  className="hover:bg-borderColor/30 cursor-pointer transition"
                >
                  <td className="p-3 font-mono text-gray-300">#{pos.ticket}</td>
                  <td className="p-3 font-bold text-white">{pos.symbol}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      pos.type === 'BUY' ? 'bg-accentGreen/10 text-accentGreen border border-accentGreen/30' : 'bg-accentRed/10 text-accentRed border border-accentRed/30'
                    }`}>
                      {pos.type}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-gray-200">{pos.lots}</td>
                  <td className="p-3 font-mono text-gray-300">{pos.open_price}</td>
                  <td className="p-3 font-mono text-white font-semibold">{pos.current_price?.toFixed(2)}</td>
                  <td className="p-3 font-mono text-gray-400">{pos.sl || 'None'}</td>
                  <td className="p-3 font-mono text-gray-400">{pos.tp || 'None'}</td>
                  <td className={`p-3 font-bold font-mono ${pos.profit >= 0 ? 'text-accentGreen' : 'text-accentRed'}`}>
                    {pos.profit >= 0 ? `+$${pos.profit.toFixed(2)}` : `-$${Math.abs(pos.profit).toFixed(2)}`}
                  </td>
                  <td className="p-3 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => partialCloseTrade(pos.ticket, 50.0)}
                      className="px-2 py-1 bg-amber-500/15 hover:bg-amber-500/25 text-amber-400 border border-amber-500/30 rounded font-semibold text-[10px] transition"
                      title="Book 50% Lot Profit Immediately"
                    >
                      Book 50%
                    </button>
                    <button
                      onClick={() => setSelectedPosition(pos)}
                      className="p-1 text-gray-400 hover:text-white hover:bg-borderColor rounded"
                      title="Modify / Custom Partial Book"
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => closeTrade(pos.ticket)}
                      className="p-1 text-accentRed/80 hover:text-accentRed hover:bg-accentRed/10 rounded"
                      title="Close Full Trade"
                    >
                      <XCircle size={14} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
