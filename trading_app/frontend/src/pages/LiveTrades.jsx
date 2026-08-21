import React, { useState } from 'react';
import { TradeTable } from '../components/TradeTable';
import { ManualTradeModal } from '../components/ManualTradeModal';
import { TradeDrawer } from '../components/TradeDrawer';
import { sendAICommand, openPosition } from '../api/tradingApi';
import { Bot, Send, Sparkles, AlertTriangle, Check } from 'lucide-react';

export const LiveTrades = () => {
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [aiInput, setAiInput] = useState('');
  const [aiHistory, setAiHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleAiSend = async () => {
    if (!aiInput.trim() || loading) return;
    const userMsg = { sender: 'user', text: aiInput, timestamp: new Date().toLocaleTimeString() };
    setAiHistory((prev) => [...prev, userMsg]);
    const cmd = aiInput;
    setAiInput('');
    setLoading(true);

    try {
      const res = await sendAICommand(cmd);
      setAiHistory((prev) => [
        ...prev,
        {
          sender: 'gemini',
          text: res.message,
          action: res.action,
          timestamp: new Date().toLocaleTimeString()
        }
      ]);
    } catch (e) {
      setAiHistory((prev) => [
        ...prev,
        { sender: 'gemini', text: 'Error connecting to Gemini CLI engine.', timestamp: new Date().toLocaleTimeString() }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmAction = async (action) => {
    try {
      if (action.action_name === 'OPEN_TRADE') {
        await openPosition({
          symbol: action.symbol,
          direction: action.direction,
          lots: action.lots,
          sl: action.sl_pips,
          tp: action.tp_pips
        });
        setAiHistory((prev) => [
          ...prev,
          { sender: 'gemini', text: `✅ Successfully opened ${action.direction} on ${action.symbol}.`, timestamp: new Date().toLocaleTimeString() }
        ]);
      }
    } catch (e) {
      alert('Trade execution failed');
    }
  };

  return (
    <div className="space-y-6 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-bold text-white text-lg">Live Positions & Execution</h2>
          <span className="text-xs text-gray-400">Monitor active trades and command AI trade execution</span>
        </div>
      </div>

      {/* Main Table */}
      <div className="h-[400px]">
        <TradeTable onOpenManualTrade={() => setIsManualModalOpen(true)} />
      </div>

      {/* Gemini AI Command Bar Panel */}
      <div className="bg-cardBg border border-borderColor p-4 rounded-xl space-y-3">
        <div className="flex items-center gap-2 font-semibold text-white text-xs">
          <Sparkles size={16} className="text-blue-400" />
          <span>Gemini AI Trade Command Engine</span>
        </div>

        {/* Conversation history bubble stream */}
        <div className="max-h-48 overflow-y-auto space-y-2 text-xs p-3 bg-darkBg rounded-xl border border-borderColor">
          {aiHistory.length === 0 ? (
            <div className="text-gray-500 italic">Try: "Open a BUY on EURUSDm with 0.1 lots, 20 pip SL and 40 pip TP"</div>
          ) : (
            aiHistory.map((item, idx) => (
              <div key={idx} className={`p-2 rounded-lg ${item.sender === 'user' ? 'bg-accentBlue/20 text-blue-200' : 'bg-cardBg text-gray-200 border border-borderColor'}`}>
                <div className="font-semibold text-[10px] text-gray-400 uppercase">{item.sender}</div>
                <div>{item.text}</div>
                {item.action && (
                  <div className="mt-2 p-2 bg-darkBg rounded border border-blue-500/30 flex items-center justify-between">
                    <span className="font-mono text-white">Action: {item.action.direction} {item.action.symbol} ({item.action.lots} lots)</span>
                    <button
                      onClick={() => handleConfirmAction(item.action)}
                      className="px-2.5 py-1 bg-accentGreen hover:bg-accentGreen/90 text-darkBg font-bold rounded flex items-center gap-1"
                    >
                      <Check size={12} /> Confirm & Execute
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Chat input */}
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={aiInput}
            onChange={(e) => setAiInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAiSend()}
            placeholder="Ask Gemini to manage or execute a trade..."
            className="flex-1 bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-accentBlue"
          />
          <button
            onClick={handleAiSend}
            disabled={loading}
            className="px-4 py-2 bg-accentBlue hover:bg-blue-600 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition"
          >
            <Send size={14} /> Command
          </button>
        </div>
      </div>

      {/* Modals & Drawers */}
      <ManualTradeModal isOpen={isManualModalOpen} onClose={() => setIsManualModalOpen(false)} />
      <TradeDrawer />
    </div>
  );
};
