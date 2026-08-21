import React, { useState } from 'react';
import { 
  LayoutDashboard, 
  TrendingUp, 
  Settings, 
  Bot, 
  FlaskConical, 
  Terminal, 
  ChevronLeft, 
  ChevronRight 
} from 'lucide-react';

const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'trades', label: 'Live Trades', icon: TrendingUp },
  { id: 'config', label: 'Configuration', icon: Settings },
  { id: 'ai', label: 'AI Settings', icon: Bot },
  { id: 'backtest', label: 'Backtesting', icon: FlaskConical },
  { id: 'logs', label: 'Logs', icon: Terminal },
];

export const Sidebar = ({ activePage, setActivePage }) => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={`bg-cardBg border-r border-borderColor flex flex-col justify-between transition-all duration-300 ${collapsed ? 'w-16' : 'w-52'} min-h-screen z-20`}>
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
          <div>TradeBot AI v2.0</div>
          <div>Status: <span className="text-accentGreen font-semibold">Online</span></div>
        </div>
      )}
    </aside>
  );
};
