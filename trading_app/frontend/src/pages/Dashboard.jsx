import React, { useEffect, useState } from 'react';
import { useAccountStore } from '../store/accountStore';
import { usePositionsStore } from '../store/positionsStore';
import { useConfigStore } from '../store/configStore';
import { useAnalyticsStore } from '../store/analyticsStore';
import { MetricCard } from '../components/MetricCard';
import { EquityChart } from '../components/EquityChart';
import { Wallet, TrendingUp, Cpu, Award, Zap, PieChart as PieIcon, Activity, CheckCircle, AlertCircle, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const SYMBOL_COLORS = {
  XAUUSDm: '#d29922',
  BTCUSDm: '#f78166',
  USOILm: '#58a6ff',
  EURUSDm: '#00d395',
};

const DEFAULT_COLORS = ['#d29922', '#f78166', '#58a6ff', '#00d395', '#a371f7'];

export const Dashboard = () => {
  const [feedSearch, setFeedSearch] = useState('');
  const [feedDirection, setFeedDirection] = useState('ALL');
  const [feedPage, setFeedPage] = useState(1);
  const [feedPageSize, setFeedPageSize] = useState(5);

  const account = useAccountStore((state) => state.account);
  const positions = usePositionsStore((state) => state.positions);
  const config = useConfigStore((state) => state.config);
  const updateField = useConfigStore((state) => state.updateField);

  const symbolDistribution = useAnalyticsStore((state) => state.symbolDistribution);
  const activityFeed = useAnalyticsStore((state) => state.activityFeed);
  const fetchAnalytics = useAnalyticsStore((state) => state.fetchAnalytics);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const symbols = config?.SYMBOLS || {};
  const openPnl = positions.reduce((acc, p) => acc + (p.profit || 0), 0);
  const activeSymbolsCount = Object.values(symbols).filter((s) => s.enabled).length;

  // Format donut data
  const distEntries = Object.entries(symbolDistribution || {});
  const totalVolume = distEntries.reduce((sum, [, count]) => sum + count, 0);

  const donutData = distEntries.map(([sym, count]) => ({
    name: sym,
    value: count,
    pct: totalVolume > 0 ? ((count / totalVolume) * 100).toFixed(0) : 0
  }));

  const hasDonutData = donutData.length > 0 && totalVolume > 0;
  const hasActivityData = Array.isArray(activityFeed) && activityFeed.length > 0;

  // Activity Feed Filter & Pagination Logic
  const filteredFeed = (activityFeed || []).filter((act) => {
    const matchesDir = feedDirection === 'ALL' || act.direction === feedDirection;
    const matchesSearch = !feedSearch || 
      act.symbol?.toLowerCase().includes(feedSearch.toLowerCase()) ||
      act.detail?.toLowerCase().includes(feedSearch.toLowerCase()) ||
      act.time?.includes(feedSearch);
    return matchesDir && matchesSearch;
  });

  const totalFeedPages = Math.max(1, Math.ceil(filteredFeed.length / feedPageSize));
  const displayedFeed = filteredFeed.slice((feedPage - 1) * feedPageSize, feedPage * feedPageSize);

  return (
    <div className="space-y-6 pb-12">
      {/* Top 4 Metric Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Balance"
          value={`$${account.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          subtext="MT5 Account Capital"
          icon={Wallet}
        />
        <MetricCard
          title="Open Floating P&L"
          value={`${openPnl >= 0 ? '+' : ''}$${openPnl.toFixed(2)}`}
          indicator={openPnl >= 0 ? 'green' : 'red'}
          subtext="Unrealized open positions profit"
          icon={TrendingUp}
        />
        <MetricCard
          title="Active Trading Pairs"
          value={`${activeSymbolsCount} / ${Object.keys(symbols).length}`}
          subtext="Symbols enabled in config"
          icon={Cpu}
        />
        <MetricCard
          title="Daily P&L"
          value={`${account.daily_pnl >= 0 ? '+' : ''}$${account.daily_pnl.toFixed(2)}`}
          indicator={account.daily_pnl >= 0 ? 'green' : 'red'}
          subtext="Today's closed trade P&L"
          icon={Award}
        />
      </div>

      {/* Chart Section */}
      <div className="grid grid-cols-1 lg:grid-cols-10 gap-6">
        {/* Left Panel (60%) */}
        <div className="lg:col-span-6">
          <EquityChart />
        </div>

        {/* Right Panel (40%) */}
        <div className="lg:col-span-4 bg-cardBg border border-borderColor p-5 rounded-2xl flex flex-col justify-between shadow-lg">
          <div>
            <div className="flex items-center gap-2">
              <PieIcon size={18} className="text-accentBlue" />
              <h3 className="font-bold text-white text-sm">Trade Volume by Symbol</h3>
            </div>
            <span className="text-xs text-gray-400">Distribution across active positions & history</span>
          </div>

          {!hasDonutData ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center my-4 bg-darkBg/40 border border-borderColor/50 rounded-xl">
              <div className="p-3 bg-borderColor/40 rounded-full text-gray-500 mb-2">
                <PieIcon size={28} />
              </div>
              <h4 className="font-semibold text-white text-xs">No Trade Distribution Available</h4>
              <p className="text-[11px] text-gray-400 max-w-xs mt-1">
                Symbol volume distribution will populate once trades are executed on your account.
              </p>
            </div>
          ) : (
            <>
              <div className="w-full h-52 my-2">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {donutData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={SYMBOL_COLORS[entry.name] || DEFAULT_COLORS[index % DEFAULT_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#161b22', borderColor: '#30363d', borderRadius: '10px', color: '#e6edf3' }}
                      formatter={(val, name) => [`${val} trades (${((val / totalVolume) * 100).toFixed(0)}%)`, name]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                {donutData.map((d, i) => (
                  <div key={d.name} className="flex items-center gap-2 bg-darkBg/60 p-2 rounded-lg border border-borderColor/60">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: SYMBOL_COLORS[d.name] || DEFAULT_COLORS[i % DEFAULT_COLORS.length] }}
                    />
                    <span className="text-gray-200 font-semibold">{d.name}</span>
                    <span className="text-gray-500 font-mono ml-auto">{d.value} ({d.pct}%)</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Active Symbol Quick Controls Grid */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Zap size={18} className="text-amber-400" />
          <h3 className="font-bold text-white text-sm">Active Symbol Quick Controls</h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(symbols).map(([sym, data]) => (
            <div key={sym} className={`bg-cardBg border p-4 rounded-xl flex flex-col justify-between transition ${data.enabled ? 'border-borderColor shadow-md' : 'border-borderColor/40 opacity-70'}`}>
              <div className="flex items-center justify-between">
                <span className="font-bold text-white text-sm">{sym}</span>
                <button
                  onClick={() => updateField(`SYMBOLS.${sym}.enabled`, !data.enabled)}
                  className={`w-10 h-5 flex items-center rounded-full p-0.5 transition ${data.enabled ? 'bg-accentGreen' : 'bg-gray-700'}`}
                >
                  <div className={`bg-white w-4 h-4 rounded-full shadow transform transition ${data.enabled ? 'translate-x-5' : 'translate-x-0'}`} />
                </button>
              </div>

              <div className="my-3 space-y-1.5 text-xs">
                <div className="flex justify-between text-gray-400">
                  <span>Risk %:</span> <span className="text-white font-semibold">{data.risk_percent}%</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>TP Ratio:</span> <span className="text-white font-semibold">{data.tp_ratio}x</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Scalping:</span> <span className="text-white font-semibold">{data.scalping_mode ? 'ON' : 'OFF'}</span>
                </div>
              </div>

              <span className={`text-[10px] px-2 py-1 rounded-md font-bold text-center border ${
                data.enabled ? 'bg-accentGreen/10 text-accentGreen border-accentGreen/30' : 'bg-gray-800 text-gray-500 border-transparent'
              }`}>
                {data.enabled ? 'Active Trading' : 'Paused'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Activity Feed */}
      <div className="bg-cardBg border border-borderColor p-5 rounded-2xl shadow-lg space-y-4">
        {/* Header & Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-borderColor/60 pb-3">
          <div className="flex items-center gap-2">
            <Activity size={18} className="text-accentBlue" />
            <h3 className="font-bold text-white text-sm">Recent Trade Activity Feed</h3>
            {activityFeed.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-accentBlue/20 text-accentBlue border border-accentBlue/30">
                {filteredFeed.length} Events
              </span>
            )}
          </div>

          {/* Filter, Search & Page Controls */}
          {hasActivityData && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {/* Direction Filter Pills */}
              <div className="flex items-center gap-1 bg-darkBg border border-borderColor p-0.5 rounded-lg font-mono text-[11px]">
                {['ALL', 'BUY', 'SELL'].map((dir) => (
                  <button
                    key={dir}
                    onClick={() => {
                      setFeedDirection(dir);
                      setFeedPage(1);
                    }}
                    className={`px-2.5 py-0.5 rounded-md font-bold transition ${
                      feedDirection === dir
                        ? 'bg-accentBlue text-white shadow'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    {dir}
                  </button>
                ))}
              </div>

              {/* Search Box */}
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-2 text-gray-500" />
                <input
                  type="text"
                  value={feedSearch}
                  onChange={(e) => {
                    setFeedSearch(e.target.value);
                    setFeedPage(1);
                  }}
                  placeholder="Search activity..."
                  className="bg-darkBg border border-borderColor rounded-lg pl-7 pr-2.5 py-1 text-white placeholder-gray-500 focus:outline-none focus:border-accentBlue text-xs font-mono w-44"
                />
              </div>

              {/* Page Size */}
              <select
                value={feedPageSize}
                onChange={(e) => {
                  setFeedPageSize(Number(e.target.value));
                  setFeedPage(1);
                }}
                className="bg-darkBg border border-borderColor text-gray-300 rounded-lg px-2 py-1 text-xs font-mono cursor-pointer"
              >
                <option value={5}>5 / page</option>
                <option value={10}>10 / page</option>
                <option value={20}>20 / page</option>
              </select>
            </div>
          )}
        </div>

        {!hasActivityData ? (
          <div className="p-8 text-center bg-darkBg/40 border border-borderColor/50 rounded-xl my-2">
            <Activity size={28} className="mx-auto text-gray-500 mb-2" />
            <h4 className="font-semibold text-white text-xs">No Recent Trade Activity Available</h4>
            <p className="text-[11px] text-gray-400 max-w-xs mx-auto mt-1">
              Order open/close events from MetaTrader 5 will stream here in real-time.
            </p>
          </div>
        ) : filteredFeed.length === 0 ? (
          <div className="p-6 text-center bg-darkBg/40 border border-borderColor/50 rounded-xl">
            <p className="text-xs text-gray-400">No activity events match your filter criteria.</p>
          </div>
        ) : (
          <div className="space-y-2 text-xs">
            {displayedFeed.map((act, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-darkBg rounded-xl border border-borderColor/60 hover:border-borderColor transition">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-gray-400 bg-gray-800/80 px-2 py-0.5 rounded border border-gray-700/50 text-[10px] whitespace-nowrap shrink-0">
                    {act.time}
                  </span>
                  <span className={`px-2 py-0.5 rounded-md font-bold text-[10px] uppercase border shrink-0 ${
                    act.type === 'open'
                      ? 'bg-accentBlue/20 text-accentBlue border-accentBlue/30'
                      : (act.type === 'close_profit' ? 'bg-accentGreen/20 text-accentGreen border-accentGreen/30' : 'bg-accentRed/20 text-accentRed border-accentRed/30')
                  }`}>
                    {act.direction}
                  </span>
                  <span className="font-bold text-white shrink-0">{act.symbol}</span>
                </div>
                <span className="text-gray-300 font-mono text-right">{act.detail}</span>
              </div>
            ))}

            {/* Pagination Controls */}
            {filteredFeed.length > feedPageSize && (
              <div className="pt-2 flex items-center justify-between border-t border-borderColor/50 text-xs font-mono text-gray-400">
                <span className="text-[11px]">
                  Showing {(feedPage - 1) * feedPageSize + 1} - {Math.min(feedPage * feedPageSize, filteredFeed.length)} of {filteredFeed.length}
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setFeedPage((p) => Math.max(1, p - 1))}
                    disabled={feedPage === 1}
                    className="px-2.5 py-1 bg-darkBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white flex items-center gap-1"
                  >
                    <ChevronLeft size={13} /> Prev
                  </button>
                  <span className="px-2 py-0.5 bg-accentBlue/10 text-accentBlue border border-accentBlue/30 rounded font-bold text-[11px]">
                    Page {feedPage} of {totalFeedPages}
                  </span>
                  <button
                    onClick={() => setFeedPage((p) => Math.min(totalFeedPages, p + 1))}
                    disabled={feedPage >= totalFeedPages}
                    className="px-2.5 py-1 bg-darkBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white flex items-center gap-1"
                  >
                    Next <ChevronRight size={13} />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
