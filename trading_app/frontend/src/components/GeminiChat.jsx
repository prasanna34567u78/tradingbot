import React, { useState } from 'react';
import { sendAICommand, openPosition, closePosition } from '../api/tradingApi';
import { Bot, Send, X, Check, AlertTriangle, Sparkles } from 'lucide-react';

export const GeminiChat = ({ isOpen, onClose }) => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      sender: 'gemini',
      text: 'Hello! I am your Gemini AI Trading Assistant. You can command me in natural language (e.g. "Open a BUY on EURUSDm with 0.1 lots, 20 pip SL and 40 pip TP", "Close all trades", or "How is today\'s win rate?").',
      timestamp: new Date().toLocaleTimeString()
    }
  ]);
  const [loading, setLoading] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);

  if (!isOpen) return null;

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg = {
      sender: 'user',
      text: input,
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages((prev) => [...prev, userMsg]);
    const cmdText = input;
    setInput('');
    setLoading(true);

    try {
      const res = await sendAICommand(cmdText);
      if (res.type === 'action_proposal') {
        const geminiMsg = {
          sender: 'gemini',
          text: res.message,
          action: res.action,
          timestamp: new Date().toLocaleTimeString()
        };
        setMessages((prev) => [...prev, geminiMsg]);
        setPendingAction(res.action);
      } else {
        const geminiMsg = {
          sender: 'gemini',
          text: res.message,
          timestamp: new Date().toLocaleTimeString()
        };
        setMessages((prev) => [...prev, geminiMsg]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'gemini',
          text: 'Sorry, I encountered an issue processing that command.',
          timestamp: new Date().toLocaleTimeString()
        }
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
        setMessages((prev) => [
          ...prev,
          {
            sender: 'gemini',
            text: `✅ Executed ${action.direction} trade on ${action.symbol} (${action.lots} lots).`,
            timestamp: new Date().toLocaleTimeString()
          }
        ]);
      } else if (action.action_name === 'CLOSE_ALL_TRADES') {
        setMessages((prev) => [
          ...prev,
          {
            sender: 'gemini',
            text: `✅ Executed close all open positions request.`,
            timestamp: new Date().toLocaleTimeString()
          }
        ]);
      }
      setPendingAction(null);
    } catch (err) {
      alert('Failed to execute AI trade action');
    }
  };

  return (
    <div className="fixed bottom-4 right-4 w-96 max-w-[calc(100vw-2rem)] h-[520px] bg-cardBg border border-borderColor rounded-2xl shadow-2xl flex flex-col z-50 overflow-hidden">
      {/* Header */}
      <div className="p-3.5 bg-gradient-to-r from-blue-900/40 to-indigo-900/40 border-b border-borderColor flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-blue-500/20 text-blue-400 rounded-lg">
            <Sparkles size={18} />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-white">Gemini AI Assistant</h3>
            <span className="text-[10px] text-gray-400">Natural Language Trade Engine</span>
          </div>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-borderColor rounded text-gray-400 hover:text-white">
          <X size={18} />
        </button>
      </div>

      {/* Messages Feed */}
      <div className="flex-1 p-3 overflow-y-auto space-y-3 text-xs">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
            <div
              className={`max-w-[85%] p-3 rounded-2xl ${
                msg.sender === 'user'
                  ? 'bg-accentBlue text-white rounded-br-none'
                  : 'bg-darkBg border border-borderColor text-gray-200 rounded-bl-none'
              }`}
            >
              <div>{msg.text}</div>

              {/* Confirmation Card if Gemini proposes an action */}
              {msg.action && (
                <div className="mt-3 p-2.5 bg-cardBg border border-blue-500/30 rounded-xl space-y-2 text-left">
                  <div className="flex items-center gap-1.5 font-medium text-blue-400 text-[11px]">
                    <AlertTriangle size={14} /> Action Confirmation Required
                  </div>
                  <div className="font-mono text-[11px] text-gray-300 space-y-0.5">
                    <div>Action: <span className="text-white font-bold">{msg.action.action_name}</span></div>
                    {msg.action.symbol && <div>Symbol: {msg.action.symbol}</div>}
                    {msg.action.direction && <div>Direction: {msg.action.direction}</div>}
                    {msg.action.lots && <div>Lots: {msg.action.lots}</div>}
                    {msg.action.sl_pips && <div>SL: {msg.action.sl_pips} pips</div>}
                    {msg.action.tp_pips && <div>TP: {msg.action.tp_pips} pips</div>}
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      onClick={() => handleConfirmAction(msg.action)}
                      className="flex-1 py-1 px-2 bg-accentGreen text-darkBg font-bold rounded-lg hover:bg-accentGreen/90 flex items-center justify-center gap-1"
                    >
                      <Check size={14} /> Confirm
                    </button>
                    <button
                      onClick={() => setPendingAction(null)}
                      className="py-1 px-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              <span className="block text-[9px] opacity-60 text-right mt-1">{msg.timestamp}</span>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-gray-400 text-xs italic">
            <Bot size={14} className="animate-spin text-blue-400" /> Gemini thinking...
          </div>
        )}
      </div>

      {/* Quick Prompt Pill Recommendations */}
      <div className="px-3 py-1.5 bg-darkBg/50 border-t border-borderColor flex gap-1.5 overflow-x-auto text-[10px]">
        <button
          onClick={() => setInput("Open a BUY on EURUSDm with 0.1 lots, 20 pip SL and 40 pip TP")}
          className="whitespace-nowrap px-2 py-0.5 bg-borderColor/60 hover:bg-borderColor text-gray-300 rounded-full"
        >
          + Buy EURUSDm
        </button>
        <button
          onClick={() => setInput("Close all open positions")}
          className="whitespace-nowrap px-2 py-0.5 bg-borderColor/60 hover:bg-borderColor text-gray-300 rounded-full"
        >
          Close All
        </button>
        <button
          onClick={() => setInput("Show today's performance")}
          className="whitespace-nowrap px-2 py-0.5 bg-borderColor/60 hover:bg-borderColor text-gray-300 rounded-full"
        >
          Performance
        </button>
      </div>

      {/* Input Bar */}
      <div className="p-2.5 bg-darkBg border-t border-borderColor flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask Gemini to manage trades..."
          className="flex-1 bg-cardBg border border-borderColor rounded-xl px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="p-2 bg-accentBlue hover:bg-blue-600 disabled:opacity-50 text-white rounded-xl transition"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
};
