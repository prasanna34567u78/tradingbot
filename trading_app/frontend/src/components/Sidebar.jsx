import React, { useState } from 'react';
import { 
  LayoutDashboard, 
  TrendingUp, 
  Settings, 
  Bot, 
  FlaskConical, 
  Terminal, 
  ChevronLeft, 
  ChevronRight,
  X
} from 'lucide-react';

export const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'trades', label: 'Live Trades', icon: TrendingUp },
  { id: 'config', label: 'Configuration', icon: Settings },
  { id: 'ai', label: 'AI Settings', icon: Bot },
  { id: 'backtest', label: 'Backtesting', icon: FlaskConical },
  { id: 'logs', label: 'Logs', icon: Terminal },
];

export const Sidebar = ({ activePage, setActivePage, isMobileOpen, setIsMobileOpen }) => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <>
      {/* Mobile Drawer Backdrop */}
      {isMobileOpen && (
        <div 
          onClick={() => setIsMobileOpen(false)}
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 md:hidden transition-opacity"
        />
      )}

      {/* Mobile Slide-out Drawer */}
      <div className={`fixed inset-y-0 left-0 w-64 bg-cardBg border-r border-borderColor z-50 transform transition-transform duration-300 ease-in-out md:hidden flex flex-col justify-between ${
        isMobileOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div>
          <div className="p-4 border-b border-borderColor flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-bold text-base text-white">TradeBot AI</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-accentGreen/10 text-accentGreen border border-accentGreen/30">v2.6</span>
            </div>
            <button 
              onClick={() => setIsMobileOpen(false)}
              className="p-1.5 hover:bg-borderColor rounded-lg text-gray-400 hover:text-white"
            >
              <X size={20} />
            </button>
          </div>

          <nav className="p-3 space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activePage === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    setActivePage(item.id);
                    setIsMobileOpen(false);
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition ${
                    isActive 
                      ? 'bg-accentBlue text-white shadow-lg shadow-accentBlue/25' 
                      : 'text-gray-400 hover:bg-borderColor/50 hover:text-white'
                  }`}
                >
                  <Icon size={20} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="p-4 border-t border-borderColor text-xs text-gray-400 bg-darkBg/50">
          <div className="font-semibold text-white">Exness MT5 Engine</div>
          <div className="text-[11px] text-gray-500">Connected & Synced</div>
        </div>
      </div>

      {/* Desktop Persistent Left Sidebar */}
      <aside className={`hidden md:flex bg-cardBg border-r border-borderColor flex-col justify-between transition-all duration-300 ${collapsed ? 'w-16' : 'w-52'} min-h-screen z-20`}>
        <div>
          {/* Toggle Button */}
          <div className="p-3 border-b border-borderColor flex items-center justify-between">
            {!collapsed && <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Navigation</span>}
            <button 
              onClick={() => setCollapsed(!collapsed)}
              className="p-1 hover:bg-borderColor rounded text-gray-400 hover:text-white transition"
            >
              {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>
          </div>

          {/* Links */}
          <nav className="p-2 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activePage === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActivePage(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                    isActive 
                      ? 'bg-accentBlue/10 text-accentBlue border border-accentBlue/30 shadow-sm' 
                      : 'text-gray-400 hover:bg-borderColor/50 hover:text-white'
                  }`}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon size={20} className={isActive ? 'text-accentBlue' : 'text-gray-400'} />
                  {!collapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </nav>
        </div>

        {!collapsed && (
          <div className="p-4 border-t border-borderColor text-xs text-gray-500">
            <div>TradeBot AI v2.6</div>
            <div>Status: <span className="text-accentGreen font-semibold">Online</span></div>
          </div>
        )}
      </aside>
    </>
  );
};
