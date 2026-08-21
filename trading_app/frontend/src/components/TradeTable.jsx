import React from 'react';
import { usePositionsStore } from '../store/positionsStore';
import { Edit2, XCircle } from 'lucide-react';

export const TradeTable = ({ onOpenManualTrade }) => {
  const positions = usePositionsStore((state) => state.positions);
  const closeTrade = usePositionsStore((state) => state.closeTrade);
  const partialCloseTrade = usePositionsStore((state) => state.partialCloseTrade);
  const setSelectedPosition = usePositionsStore((state) => state.setSelectedPosition);

  return (
    <div className="bg-cardBg border border-borderColor rounded-xl overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-borderColor flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-white text-sm">Open Positions</h3>
          <span className="text-xs text-gray-400">Live active positions stream</span>
        </div>
        <button
          onClick={onOpenManualTrade}
          className="px-3 py-1.5 bg-accentBlue hover:bg-blue-600 text-white rounded-lg text-xs font-semibold transition"
        >
          + Manual Trade
        </button>
      </div>

      <div className="overflow-x-auto flex-1">
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
