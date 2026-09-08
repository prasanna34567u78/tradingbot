import React, { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useConfigStore } from './store/configStore';
import { Sidebar } from './components/Sidebar';
import { TopHeader } from './components/TopHeader';
import { GeminiChat } from './components/GeminiChat';
import { Login } from './pages/Login';

import { Dashboard } from './pages/Dashboard';
import { LiveTrades } from './pages/LiveTrades';
import { Configuration } from './pages/Configuration';
import { AISettings } from './pages/AISettings';
import { Backtesting } from './pages/Backtesting';
import { Logs } from './pages/Logs';
import { LayoutDashboard, TrendingUp, Settings, Terminal, Bot, LogOut } from 'lucide-react';

// ── Auth helper ──────────────────────────────────────────────────────────────
function isAuthenticated() {
  const token = sessionStorage.getItem('auth_token');
  const user  = sessionStorage.getItem('auth_user');
  return !!(token && user === 'prasanna');
}

function logout() {
  sessionStorage.removeItem('auth_token');
  sessionStorage.removeItem('auth_user');
}

// ── Main App ─────────────────────────────────────────────────────────────────
export function App() {
  const [authed, setAuthed] = useState(isAuthenticated());

  // Re-check auth on every render (handles tab dup etc.)
  useEffect(() => {
    setAuthed(isAuthenticated());
  }, []);

  // Show login wall if not authenticated
  if (!authed) {
    return <Login onLoginSuccess={() => setAuthed(true)} />;
  }

  return <MainApp onLogout={() => { logout(); setAuthed(false); }} />;
}

// ── Authenticated Shell ───────────────────────────────────────────────────────
function MainApp({ onLogout }) {
  useWebSocket();
  const fetchConfig = useConfigStore((state) => state.fetchConfig);

  const [activePage, setActivePage] = useState('dashboard');
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isGeminiOpen, setIsGeminiOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard':  return <Dashboard />;
      case 'trades':     return <LiveTrades />;
      case 'config':     return <Configuration />;
      case 'ai':         return <AISettings />;
      case 'backtest':   return <Backtesting />;
      case 'logs':       return <Logs />;
      default:           return <Dashboard />;
    }
  };

  const mobileTabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'trades',    label: 'Trades',    icon: TrendingUp },
    { id: 'config',    label: 'Settings',  icon: Settings },
    { id: 'logs',      label: 'Logs',      icon: Terminal },
    { id: 'ai',        label: 'AI & Bot',  icon: Bot },
  ];

  return (
    <div className="flex min-h-screen bg-darkBg text-gray-100 antialiased font-sans">
      {/* Sidebar */}
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
        isMobileOpen={isMobileOpen}
        setIsMobileOpen={setIsMobileOpen}
      />

      {/* Main viewport */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header — with Logout button injected */}
        <div className="relative">
          <TopHeader
            onOpenGemini={() => setIsGeminiOpen(true)}
            onToggleMobileMenu={() => setIsMobileOpen((prev) => !prev)}
          />
          {/* Logout button — top-right corner overlay */}
          <button
            onClick={() => setShowLogoutConfirm(true)}
            title="Sign Out"
            className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-gray-400 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all z-50"
          >
            <LogOut size={14} />
            <span className="hidden sm:inline">Sign Out</span>
          </button>
        </div>

        <main className="flex-1 p-3 sm:p-6 pb-24 md:pb-8 overflow-y-auto">
          {renderPage()}
        </main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 bg-cardBg/95 backdrop-blur-md border-t border-borderColor md:hidden flex justify-around items-center py-2 px-1 shadow-2xl">
        {mobileTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activePage === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActivePage(tab.id)}
              className={`flex flex-col items-center justify-center flex-1 py-1 transition ${
                isActive ? 'text-accentBlue' : 'text-gray-400 hover:text-white'
              }`}
            >
              <Icon size={20} className={isActive ? 'text-accentBlue' : 'text-gray-400'} />
              <span className={`text-[10px] mt-0.5 font-semibold ${isActive ? 'text-accentBlue' : 'text-gray-400'}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Gemini Chat */}
      <GeminiChat isOpen={isGeminiOpen} onClose={() => setIsGeminiOpen(false)} />

      {/* Logout Confirmation Modal */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-cardBg border border-borderColor rounded-2xl shadow-2xl p-6 w-full max-w-sm mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-500/15 flex items-center justify-center">
                <LogOut size={20} className="text-red-400" />
              </div>
              <div>
                <h3 className="text-white font-bold text-base">Sign Out?</h3>
                <p className="text-gray-400 text-xs">You will need to log in again to access the bot.</p>
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="flex-1 py-2.5 rounded-xl border border-borderColor text-gray-300 hover:bg-white/5 text-sm font-medium transition"
              >
                Cancel
              </button>
              <button
                onClick={onLogout}
                className="flex-1 py-2.5 rounded-xl bg-red-500 hover:bg-red-600 text-white text-sm font-bold transition"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
