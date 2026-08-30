import React, { useState, useEffect } from 'react';
import { useAccountStore } from '../store/accountStore';
import { useConfigStore } from '../store/configStore';
import { startBot, stopBot, getBotStatus } from '../api/tradingApi';
import { EditAccountModal } from './EditAccountModal';
import { formatCurrency } from '../utils/formatters';
import { Play, Square, Bot, Cpu, Edit3, Settings, Menu } from 'lucide-react';

export const TopHeader = ({ onOpenGemini, onToggleMobileMenu }) => {
  const account = useAccountStore((state) => state.account);
  const botRunning = useAccountStore((state) => state.botRunning);
  const setBotRunning = useAccountStore((state) => state.setBotRunning);
  const wsConnected = useAccountStore((state) => state.wsConnected);
  const config = useConfigStore((state) => state.config);

  const [isEditAccountOpen, setIsEditAccountOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const strategyMode = config?.STRATEGY_MODE || 'mcp_enhanced';
  const currency = account?.currency || 'USD';

  // Sync bot status from backend on mount (before WebSocket kicks in)
  useEffect(() => {
    getBotStatus()
      .then((data) => {
        if (typeof data?.running === 'boolean') setBotRunning(data.running);
      })
      .catch(() => {});
  }, []);

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const handleToggleBot = async () => {
    setLoading(true);
    try {
      if (botRunning) {
        await stopBot();
        setBotRunning(false);
        showToast('Trading Bot stopped successfully.', 'success');
      } else {
        const res = await startBot();
        if (res?.status === 'warning') {
          showToast(res.message || 'No symbols enabled. Go to Symbol Configuration first.', 'error');
          setLoading(false);
          return;
        }
        setBotRunning(true);
        if (res?.status === 'already_running') {
          showToast('Trading Bot is already active and running.', 'success');
        } else {
          const cfg = res?.config;
          const detail = cfg
            ? ` Mode: ${cfg.strategy_mode?.toUpperCase() || 'PDE'} | Symbols: ${(cfg.enabled_symbols || []).join(', ')}`
            : '';
          showToast(`Trading Bot started successfully!${detail}`, 'success');
        }
      }
    } catch (e) {
      console.error('Failed to toggle bot:', e);
      try {
        const st = await getBotStatus();
        if (st && typeof st.running === 'boolean') {
          setBotRunning(st.running);
          showToast(st.running ? 'Trading Bot is running.' : 'Trading Bot is stopped.', 'info');
          setLoading(false);
          return;
        }
      } catch (err) {}
      showToast('Failed to toggle bot. Ensure API server (http://127.0.0.1:8000) is active.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-20 right-4 z-50 px-4 py-3 rounded-xl shadow-2xl text-sm font-semibold flex items-center gap-2 border transition animate-fade-in ${
            toast.type === 'success'
              ? 'bg-accentGreen/10 border-accentGreen/40 text-accentGreen'
              : 'bg-accentRed/10 border-accentRed/40 text-accentRed'
          }`}
        >
          <span>{toast.type === 'success' ? '✓' : '✗'}</span>
          {toast.msg}
        </div>
      )}

      <header className="h-16 bg-cardBg border-b border-borderColor px-3 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-md">
        {/* Left: Hamburger (Mobile) + App Logo & Strategy Badge */}
        <div className="flex items-center gap-2 sm:gap-4">
          {/* Mobile Hamburger Menu Button */}
          <button
            onClick={onToggleMobileMenu}
            className="p-2 -ml-1 text-gray-400 hover:text-white hover:bg-borderColor rounded-lg md:hidden transition"
            title="Open Navigation Menu"
          >
            <Menu size={22} />
          </button>

          <div className="flex items-center gap-2.5">
            <img 
              src="/quantbotlogo.png" 
              alt="QuantBot AI Logo" 
              className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl object-contain shadow-md border border-borderColor/40 bg-darkBg/60 p-0.5"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
            <div>
              <h1 className="font-bold text-sm sm:text-base text-white leading-tight flex items-center gap-1.5">
                QuantBot <span className="text-accentBlue font-black text-xs px-1.5 py-0.2 bg-accentBlue/10 border border-accentBlue/30 rounded">AI</span>
              </h1>
              <div className="text-[9px] sm:text-[10px] text-gray-400 font-mono hidden sm:block">@quantbot_ai • Exness MT5</div>
            </div>
          </div>

          <span
            className={`hidden sm:inline-block px-2.5 py-0.5 sm:py-1 rounded-full text-[10px] sm:text-xs font-semibold uppercase tracking-wider border ${
              strategyMode === 'mcp_enhanced'
                ? 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                : strategyMode === 'scalping'
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                : 'bg-blue-500/10 text-blue-400 border-blue-500/30'
            }`}
          >
            {strategyMode.replace('_', ' ')}
          </span>
        </div>

        {/* Center: Live Account Stats */}
        <div className="hidden md:flex items-center gap-5 bg-darkBg/60 px-5 py-1.5 rounded-xl border border-borderColor/60 text-xs">
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Balance</span>
            <span className="font-bold text-white">{formatCurrency(account.balance, currency)}</span>
          </div>
          <div className="h-6 w-px bg-borderColor" />
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Equity</span>
            <span className="font-bold text-white">{formatCurrency(account.equity, currency)}</span>
          </div>
          <div className="h-6 w-px bg-borderColor" />
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Free Margin</span>
            <span className="font-semibold text-gray-300">{formatCurrency(account.free_margin, currency)}</span>
          </div>
          <div className="h-6 w-px bg-borderColor" />
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Daily P&L</span>
            <span
              className={`font-semibold ${account.daily_pnl >= 0 ? 'text-accentGreen' : 'text-accentRed'}`}
            >
              {account.daily_pnl >= 0
                ? `+${formatCurrency(account.daily_pnl, currency)}`
                : formatCurrency(account.daily_pnl, currency)}
            </span>
          </div>

          <button
            onClick={() => setIsEditAccountOpen(true)}
            className="ml-2 p-1.5 bg-borderColor/60 hover:bg-borderColor text-gray-300 hover:text-white rounded-lg transition"
            title="Edit Account Details"
          >
            <Edit3 size={14} />
          </button>
        </div>

        {/* Right: Bot Control & Gemini Button */}
        <div className="flex items-center gap-3">
          <span
            className={`h-2.5 w-2.5 rounded-full ${wsConnected ? 'bg-accentGreen shadow-[0_0_8px_#00d395]' : 'bg-accentRed'}`}
            title={wsConnected ? 'WebSocket Connected' : 'WebSocket Disconnected'}
          />

          <div
            className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1.5 border ${
              botRunning
                ? 'bg-accentGreen/10 text-accentGreen border-accentGreen/30'
                : 'bg-accentRed/10 text-accentRed border-accentRed/30'
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${botRunning ? 'bg-accentGreen animate-pulse' : 'bg-accentRed'}`}
            />
            {botRunning ? 'Running' : 'Stopped'}
          </div>

          <button
            onClick={handleToggleBot}
            disabled={loading}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition shadow-sm disabled:opacity-60 disabled:cursor-wait ${
              botRunning
                ? 'bg-accentRed/20 hover:bg-accentRed/30 text-accentRed border border-accentRed/40'
                : 'bg-accentGreen hover:bg-accentGreen/90 text-darkBg border border-accentGreen'
            }`}
          >
            {loading ? (
              <span className="h-3.5 w-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : botRunning ? (
              <Square size={14} />
            ) : (
              <Play size={14} />
            )}
            {loading
              ? botRunning
                ? 'Stopping...'
                : 'Starting...'
              : botRunning
              ? 'Stop Bot'
              : 'Start Bot'}
          </button>

          <button
            onClick={onOpenGemini}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg text-xs font-semibold transition shadow-md border border-blue-400/30"
          >
            <Bot size={16} />
            Gemini AI
          </button>
        </div>
      </header>

      {/* Edit Account Modal */}
      <EditAccountModal isOpen={isEditAccountOpen} onClose={() => setIsEditAccountOpen(false)} />
    </>
  );
};
