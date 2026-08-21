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

export function App() {
  useWebSocket();
  const fetchConfig = useConfigStore((state) => state.fetchConfig);

  const [activePage, setActivePage] = useState('dashboard');
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

  return (
    <div className="flex min-h-screen bg-darkBg text-gray-100 antialiased font-sans">
      {/* Persistent Left Sidebar */}
      <Sidebar activePage={activePage} setActivePage={setActivePage} />

      {/* Main Content Viewport */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <TopHeader onOpenGemini={() => setIsGeminiOpen(true)} />

        {/* Dynamic Page Component */}
        <main className="flex-1 p-6 overflow-y-auto">
          {renderPage()}
        </main>
      </div>

      {/* Floating Gemini AI Chat Assistant */}
      <GeminiChat isOpen={isGeminiOpen} onClose={() => setIsGeminiOpen(false)} />
    </div>
  );
}

export default App;
