import React, { useState, useEffect } from 'react';
import { useAccountStore } from '../store/accountStore';
import { X, Save, Database, RefreshCw } from 'lucide-react';

export const EditAccountModal = ({ isOpen, onClose }) => {
  const account = useAccountStore((state) => state.account);
  const saveAccountEdit = useAccountStore((state) => state.saveAccountEdit);

  const [balance, setBalance] = useState(2000.00);
  const [equity, setEquity] = useState(4998.03);
  const [margin, setMargin] = useState(1.58);
  const [freeMargin, setFreeMargin] = useState(4996.45);
  const [dailyPnl, setDailyPnl] = useState(104.10);
  const [overrideEnabled, setOverrideEnabled] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (account) {
      setBalance(account.balance || 0);
      setEquity(account.equity || 0);
      setMargin(account.margin || 0);
      setFreeMargin(account.free_margin || 0);
      setDailyPnl(account.daily_pnl || 0);
      setOverrideEnabled(account.override_enabled ?? 0);
    }
  }, [account, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await saveAccountEdit({
        balance: parseFloat(balance),
        equity: parseFloat(equity),
        margin: parseFloat(margin),
        free_margin: parseFloat(freeMargin),
        daily_pnl: parseFloat(dailyPnl),
        override_enabled: overrideEnabled
      });
      onClose();
    } catch (err) {
      alert('Failed to save account changes');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-darkBg/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-cardBg border border-borderColor rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-borderColor pb-3">
          <div className="flex items-center gap-2">
            <Database size={18} className="text-accentBlue" />
            <h3 className="font-bold text-white text-base">Edit Account Details (SQLite DB)</h3>
          </div>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white rounded">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Mode Switch: Live MT5 Sync vs Manual DB Edit */}
          <div className="p-3 bg-darkBg rounded-xl border border-borderColor flex items-center justify-between">
            <div>
              <span className="font-bold text-white block">Manual DB Override</span>
              <span className="text-[10px] text-gray-400">If enabled, uses custom values instead of live MT5</span>
            </div>
            <button
              type="button"
              onClick={() => setOverrideEnabled(overrideEnabled === 1 ? 0 : 1)}
              className={`w-11 h-6 flex items-center rounded-full p-1 transition ${overrideEnabled === 1 ? 'bg-accentBlue' : 'bg-gray-700'}`}
            >
              <div className={`bg-white w-4 h-4 rounded-full shadow transform transition ${overrideEnabled === 1 ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Balance ($)</label>
              <input
                type="number"
                step="0.01"
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono"
              />
            </div>
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Equity ($)</label>
              <input
                type="number"
                step="0.01"
                value={equity}
                onChange={(e) => setEquity(e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Used Margin ($)</label>
              <input
                type="number"
                step="0.01"
                value={margin}
                onChange={(e) => setMargin(e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono"
              />
            </div>
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Free Margin ($)</label>
              <input
                type="number"
                step="0.01"
                value={freeMargin}
                onChange={(e) => setFreeMargin(e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-gray-300 font-semibold mb-1">Daily P&L ($)</label>
            <input
              type="number"
              step="0.01"
              value={dailyPnl}
              onChange={(e) => setDailyPnl(e.target.value)}
              className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-accentGreen hover:bg-accentGreen/90 text-darkBg font-bold rounded-xl transition flex items-center justify-center gap-1.5 text-sm"
          >
            <Save size={16} /> Save & Apply to DB
          </button>
        </form>
      </div>
    </div>
  );
};
