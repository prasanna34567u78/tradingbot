import React, { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useConfigStore } from './store/configStore';
import { Sidebar } from './components/Sidebar';
import { TopHeader } from './components/TopHeader';
import { GeminiChat } from './components/GeminiChat';

import { Dashboard } from './pages/Dashboard';
import { LiveTrades } from './pages/LiveTrades';
import { Configuration } from './pages/Configuration';
import { AISettings } from './pages/AISettings';
import { Backtesting } from './pages/Backtesting';
import { Logs } from './pages/Logs';
import { LayoutDashboard, TrendingUp, Settings, Terminal, Bot } from 'lucide-react';

export function App() {
  useWebSocket();
  const fetchConfig = useConfigStore((state) => state.fetchConfig);

  const [activePage, setActivePage] = useState('dashboard');
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isGeminiOpen, setIsGeminiOpen] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard':
        return <Dashboard />;
      case 'trades':
        return <LiveTrades />;
      case 'config':
        return <Configuration />;
      case 'ai':
        return <AISettings />;
      case 'backtest':
        return <Backtesting />;
      case 'logs':
        return <Logs />;
      default:
        return <Dashboard />;
    }
  };

  const mobileTabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'trades', label: 'Trades', icon: TrendingUp },
    { id: 'config', label: 'Settings', icon: Settings },
    { id: 'logs', label: 'Logs', icon: Terminal },
    { id: 'ai', label: 'AI & Bot', icon: Bot },
  ];

  return (
    <div className="flex min-h-screen bg-darkBg text-gray-100 antialiased font-sans">
      {/* Persistent Left Sidebar (Desktop) + Slide Drawer (Mobile) */}
      <Sidebar 
        activePage={activePage} 
        setActivePage={setActivePage} 
        isMobileOpen={isMobileOpen} 
        setIsMobileOpen={setIsMobileOpen} 
      />

      {/* Main Content Viewport */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <TopHeader 
          onOpenGemini={() => setIsGeminiOpen(true)} 
          onToggleMobileMenu={() => setIsMobileOpen((prev) => !prev)}
        />

        {/* Dynamic Page Component */}
        <main className="flex-1 p-3 sm:p-6 pb-24 md:pb-8 overflow-y-auto">
          {renderPage()}
        </main>
      </div>

      {/* Mobile Sticky Bottom Navigation Bar */}
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

      {/* Floating Gemini AI Chat Assistant */}
      <GeminiChat isOpen={isGeminiOpen} onClose={() => setIsGeminiOpen(false)} />
    </div>
  );
}

export default App;
