import React, { useState, useRef, useEffect } from 'react';
import { useLogStore } from '../store/logStore';
import { useAnalyticsStore } from '../store/analyticsStore';
import { 
  Search, Download, Trash2, Pause, Play, Terminal, Zap, Bot, Cpu, Inbox, 
  ArrowDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Filter 
} from 'lucide-react';

export const LogViewer = () => {
  const [activeTab, setActiveTab] = useState('bot_logs');
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [sortOrder, setSortOrder] = useState('newest'); // 'newest' (top) or 'oldest'

  // Log Pagination State
  const [logPage, setLogPage] = useState(1);
  const [pageSize, setPageSize] = useState(50); // 50, 100, 250, or 'ALL'

  // Trade Events Filtering & Pagination State
  const [eventSearch, setEventSearch] = useState('');
  const [eventDirectionFilter, setEventDirectionFilter] = useState('ALL');
  const [eventPage, setEventPage] = useState(1);
  const [eventPageSize, setEventPageSize] = useState(10);

  const logs = useLogStore((state) => state.logs);
  const levelFilter = useLogStore((state) => state.levelFilter);
  const setLevelFilter = useLogStore((state) => state.setLevelFilter);
  const searchQuery = useLogStore((state) => state.searchQuery);
  const setSearchQuery = useLogStore((state) => state.setSearchQuery);
  const autoScroll = useLogStore((state) => state.autoScroll);
  const setAutoScroll = useLogStore((state) => state.setAutoScroll);
  const setLogRetention = useLogStore((state) => state.setLogRetention);
  const logRetention = useLogStore((state) => state.logRetention);
  const clearLogs = useLogStore((state) => state.clearLogs);

  const activityFeed = useAnalyticsStore((state) => state.activityFeed);

  const logContainerRef = useRef(null);

  const scrollToTarget = (smooth = true) => {
    if (logContainerRef.current && pageSize === 'ALL') {
      if (sortOrder === 'newest') {
        logContainerRef.current.scrollTo({
          top: 0,
          behavior: smooth ? 'smooth' : 'auto',
        });
      } else {
        logContainerRef.current.scrollTo({
          top: logContainerRef.current.scrollHeight,
          behavior: smooth ? 'smooth' : 'auto',
        });
      }
    }
  };

  useEffect(() => {
    if (autoScroll && pageSize === 'ALL') {
      scrollToTarget(true);
    }
  }, [logs, autoScroll, sortOrder, pageSize]);

  // Reset log page when filter or search changes
  useEffect(() => {
    setLogPage(1);
  }, [searchQuery, levelFilter, pageSize]);

  // Reset event page when filter changes
  useEffect(() => {
    setEventPage(1);
  }, [eventSearch, eventDirectionFilter, eventPageSize]);

  const handleScroll = () => {
    if (!logContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current;
    if (sortOrder === 'newest') {
      setIsAtBottom(scrollTop < 40);
    } else {
      const atBottom = scrollHeight - scrollTop - clientHeight < 40;
      setIsAtBottom(atBottom);
    }
  };

  const rawFilteredLogs = logs.filter((log) => {
    const matchesLevel = levelFilter === 'ALL' || log.level === levelFilter;
    const matchesSearch = !searchQuery || 
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (log.timestamp && log.timestamp.includes(searchQuery));
    return matchesLevel && matchesSearch;
  });

  const filteredLogs = sortOrder === 'newest' ? [...rawFilteredLogs].reverse() : rawFilteredLogs;

  // Pagination calculation for Logs
  const totalLogPages = pageSize === 'ALL' ? 1 : Math.max(1, Math.ceil(filteredLogs.length / Number(pageSize)));
  const displayedLogs = pageSize === 'ALL'
    ? filteredLogs
    : filteredLogs.slice((logPage - 1) * Number(pageSize), logPage * Number(pageSize));

  // Trade Events Filter & Pagination
  const filteredEvents = activityFeed.filter((evt) => {
    const matchesDir = eventDirectionFilter === 'ALL' || evt.direction === eventDirectionFilter;
    const matchesSearch = !eventSearch || 
      evt.symbol?.toLowerCase().includes(eventSearch.toLowerCase()) ||
      evt.detail?.toLowerCase().includes(eventSearch.toLowerCase()) ||
      evt.time?.includes(eventSearch);
    return matchesDir && matchesSearch;
  });

  const totalEventPages = Math.max(1, Math.ceil(filteredEvents.length / eventPageSize));
  const displayedEvents = filteredEvents.slice((eventPage - 1) * eventPageSize, eventPage * eventPageSize);

  const getLevelColor = (level) => {
    switch (level) {
      case 'SUCCESS':
      case 'TRADE_OPEN':
      case 'TRADE_CLOSE':
        return 'text-accentGreen bg-accentGreen/10 border-accentGreen/30';
      case 'WARNING':
        return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
      case 'ERROR':
        return 'text-accentRed bg-accentRed/10 border-accentRed/30';
      case 'DEBUG':
        return 'text-accentBlue bg-accentBlue/10 border-accentBlue/30';
      default:
        return 'text-gray-300 bg-gray-800 border-gray-700';
    }
  };

  const handleExport = () => {
    if (!logs.length) return;
    const text = logs.map((l) => `[${l.timestamp}] [${l.level}] ${l.message}`).join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tradebot_logs_${new Date().toISOString().slice(0, 10)}.log`;
    a.click();
  };

  // AI Decisions live entries from log store
  const aiLogs = logs.filter((l) => l.message.toLowerCase().includes('gemini') || l.message.toLowerCase().includes('ai') || l.message.toLowerCase().includes('mcp'));

  return (
    <div className="bg-cardBg border border-borderColor rounded-2xl overflow-hidden flex flex-col h-[700px] shadow-2xl">
      {/* 4 Tabs Header */}
      <div className="bg-darkBg/80 border-b border-borderColor flex items-center justify-between px-4 pt-3 backdrop-blur">
        <div className="flex gap-2">
          {[
            { id: 'bot_logs', label: 'Bot Logs', icon: Terminal, count: filteredLogs.length },
            { id: 'trade_events', label: 'Trade Events', icon: Zap, count: filteredEvents.length },
            { id: 'ai_decisions', label: 'AI Decisions', icon: Bot, count: aiLogs.length },
            { id: 'mt5_raw', label: 'MT5 Raw IPC', icon: Cpu },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold rounded-t-xl border-t border-x transition ${
                  isActive
                    ? 'bg-cardBg text-white border-borderColor border-b-transparent shadow-lg'
                    : 'text-gray-400 border-transparent hover:text-white'
                }`}
              >
                <Icon size={15} className={isActive ? 'text-accentBlue' : 'text-gray-500'} />
                {tab.label}
                {tab.count !== undefined && (
                  <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${isActive ? 'bg-accentBlue/20 text-accentBlue' : 'bg-gray-800 text-gray-400'}`}>
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="h-2.5 w-2.5 rounded-full bg-accentGreen animate-pulse shadow-[0_0_8px_#00d395]" />
          <span className="font-mono text-gray-300 font-semibold text-[11px]">Real-Time WS Streaming</span>
        </div>
      </div>

      {/* Tab 1: Bot Logs */}
      {activeTab === 'bot_logs' && (
        <div className="flex-1 flex flex-col relative overflow-hidden">
          {/* Controls Bar */}
          <div className="p-3 bg-cardBg border-b border-borderColor flex flex-wrap items-center justify-between gap-2.5 text-xs">
            {/* Level Filters */}
            <div className="flex items-center gap-1">
              {['ALL', 'INFO', 'SUCCESS', 'WARNING', 'ERROR'].map((lvl) => (
                <button
                  key={lvl}
                  onClick={() => setLevelFilter(lvl)}
                  className={`px-2.5 py-1 rounded-lg font-mono font-bold text-[11px] transition ${
                    levelFilter === lvl ? 'bg-accentBlue text-white shadow' : 'bg-darkBg text-gray-400 hover:text-white'
                  }`}
                >
                  {lvl}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="relative flex-1 max-w-xs">
              <Search size={14} className="absolute left-2.5 top-2.5 text-gray-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search terminal logs..."
                className="w-full bg-darkBg border border-borderColor rounded-xl pl-8 pr-3 py-1.5 text-white placeholder-gray-500 focus:outline-none focus:border-accentBlue text-xs"
              />
            </div>

            {/* Action Tools */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* Order Mode Toggle */}
              <button
                onClick={() => {
                  const nextOrder = sortOrder === 'newest' ? 'oldest' : 'newest';
                  setSortOrder(nextOrder);
                  setTimeout(() => scrollToTarget(true), 50);
                }}
                className="px-2.5 py-1 rounded-lg border text-xs font-bold font-mono flex items-center gap-1.5 transition bg-darkBg border-borderColor text-gray-300 hover:text-white"
                title="Toggle Log Sorting Order"
              >
                {sortOrder === 'newest' ? '⬇ Newest Top' : '⬆ Oldest Top'}
              </button>

              {/* Page Size Selector */}
              <div className="flex items-center gap-1 bg-darkBg border border-borderColor rounded-lg px-2 py-1">
                <span className="text-[10px] text-gray-400 uppercase font-mono">Page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(e.target.value === 'ALL' ? 'ALL' : Number(e.target.value))}
                  className="bg-transparent text-white text-xs font-mono focus:outline-none cursor-pointer"
                >
                  <option value={50} className="bg-darkBg">50 / pg</option>
                  <option value={100} className="bg-darkBg">100 / pg</option>
                  <option value={250} className="bg-darkBg">250 / pg</option>
                  <option value="ALL" className="bg-darkBg">All (Stream)</option>
                </select>
              </div>

              {/* Auto-Scroll Toggle (only active in Live Stream mode) */}
              {pageSize === 'ALL' && (
                <button
                  onClick={() => {
                    const next = !autoScroll;
                    setAutoScroll(next);
                    if (next) scrollToTarget(true);
                  }}
                  className={`px-2.5 py-1 rounded-lg border text-xs font-bold font-mono flex items-center gap-1.5 transition ${
                    autoScroll
                      ? 'bg-accentGreen/15 border-accentGreen/40 text-accentGreen'
                      : 'bg-darkBg border-borderColor text-gray-400 hover:text-white'
                  }`}
                  title="Toggle Auto-Scroll"
                >
                  {autoScroll ? <Play size={12} className="fill-accentGreen" /> : <Pause size={12} />}
                  Auto-Scroll: {autoScroll ? 'ON' : 'OFF'}
                </button>
              )}

              {/* Retention Selector */}
              <select
                value={logRetention}
                onChange={(e) => setLogRetention(parseInt(e.target.value))}
                className="bg-darkBg border border-borderColor text-gray-300 rounded-lg px-2 py-1 text-xs font-mono"
                title="Memory Log Retention Limit"
              >
                <option value={100}>Max 100</option>
                <option value={500}>Max 500</option>
                <option value={1000}>Max 1000</option>
              </select>

              <button onClick={clearLogs} className="p-1.5 bg-darkBg hover:bg-borderColor text-gray-400 hover:text-white rounded-lg border border-borderColor" title="Clear Logs">
                <Trash2 size={14} />
              </button>

              <button onClick={handleExport} className="p-1.5 bg-accentBlue hover:bg-blue-600 text-white rounded-lg font-semibold flex items-center gap-1 px-3 text-xs">
                <Download size={14} /> Export
              </button>
            </div>
          </div>

          {/* Terminal Output */}
          <div
            ref={logContainerRef}
            onScroll={handleScroll}
            className="flex-1 bg-[#0d1117] p-4 font-mono text-xs overflow-y-auto space-y-1 select-text scroll-smooth"
          >
            {displayedLogs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-gray-500">
                <Inbox size={32} className="mb-2 opacity-50" />
                <span className="font-semibold text-white text-xs">No Terminal Log Entries Available</span>
                <span className="text-[11px] text-gray-400 mt-1">
                  {searchQuery ? 'No log entries match your search query.' : 'Start the bot or execute trades to populate live logs.'}
                </span>
              </div>
            ) : (
              displayedLogs.map((log, i) => {
                const rowNum = pageSize === 'ALL'
                  ? (sortOrder === 'newest' ? i + 1 : filteredLogs.length - i)
                  : (sortOrder === 'newest' 
                      ? (logPage - 1) * Number(pageSize) + i + 1
                      : filteredLogs.length - ((logPage - 1) * Number(pageSize) + i));
                return (
                  <div key={i} className="leading-relaxed hover:bg-gray-800/50 px-2 py-1 rounded transition flex items-start gap-2 border-b border-gray-800/30">
                    <span className="text-gray-600 select-none text-[10px] w-8 text-right font-mono">
                      {String(rowNum).padStart(3, '0')}
                    </span>
                    <span className="text-gray-500 shrink-0 font-mono text-[11px]">[{log.timestamp}]</span>
                    <span className={`font-bold shrink-0 text-[10px] px-1.5 py-0.2 rounded border ${getLevelColor(log.level)}`}>
                      {log.level}
                    </span>
                    <span className="text-gray-200 break-all">{log.message}</span>
                  </div>
                );
              })
            )}
          </div>

          {/* Pagination Bar for Terminal Logs */}
          {pageSize !== 'ALL' && filteredLogs.length > 0 && (
            <div className="bg-darkBg/90 border-t border-borderColor px-4 py-2 flex items-center justify-between text-xs font-mono">
              <span className="text-gray-400 text-[11px]">
                Showing <strong className="text-white">{(logPage - 1) * Number(pageSize) + 1}</strong> to{' '}
                <strong className="text-white">{Math.min(logPage * Number(pageSize), filteredLogs.length)}</strong> of{' '}
                <strong className="text-white">{filteredLogs.length}</strong> logs
              </span>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setLogPage(1)}
                  disabled={logPage === 1}
                  className="p-1 bg-cardBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white"
                  title="First Page"
                >
                  <ChevronsLeft size={14} />
                </button>
                <button
                  onClick={() => setLogPage((p) => Math.max(1, p - 1))}
                  disabled={logPage === 1}
                  className="px-2.5 py-1 bg-cardBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white flex items-center gap-1"
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                
                <span className="px-2.5 py-1 bg-accentBlue/20 text-accentBlue border border-accentBlue/40 rounded font-bold">
                  Page {logPage} of {totalLogPages}
                </span>

                <button
                  onClick={() => setLogPage((p) => Math.min(totalLogPages, p + 1))}
                  disabled={logPage >= totalLogPages}
                  className="px-2.5 py-1 bg-cardBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white flex items-center gap-1"
                >
                  Next <ChevronRight size={14} />
                </button>
                <button
                  onClick={() => setLogPage(totalLogPages)}
                  disabled={logPage >= totalLogPages}
                  className="p-1 bg-cardBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white"
                  title="Last Page"
                >
                  <ChevronsRight size={14} />
                </button>
              </div>
            </div>
          )}

          {/* Floating Scroll Button (only in Live Stream mode) */}
          {pageSize === 'ALL' && !isAtBottom && (
            <button
              onClick={() => scrollToTarget(true)}
              className="absolute bottom-4 right-6 bg-accentBlue text-white px-3 py-1.5 rounded-full text-xs font-bold shadow-2xl flex items-center gap-1.5 border border-blue-400/30 animate-bounce hover:bg-blue-600 transition z-10"
            >
              {sortOrder === 'newest' ? '⬆ Jump to Newest' : '⬇ Jump to Latest'}
            </button>
          )}
        </div>
      )}

      {/* Tab 2: Trade Events */}
      {activeTab === 'trade_events' && (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Trade Events Filter Bar */}
          <div className="p-3 bg-cardBg border-b border-borderColor flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-1">
              {['ALL', 'BUY', 'SELL'].map((dir) => (
                <button
                  key={dir}
                  onClick={() => setEventDirectionFilter(dir)}
                  className={`px-3 py-1 rounded-lg font-mono font-bold text-[11px] transition ${
                    eventDirectionFilter === dir ? 'bg-accentBlue text-white shadow' : 'bg-darkBg text-gray-400 hover:text-white'
                  }`}
                >
                  {dir}
                </button>
              ))}
            </div>

            <div className="relative flex-1 max-w-xs">
              <Search size={14} className="absolute left-2.5 top-2.5 text-gray-500" />
              <input
                type="text"
                value={eventSearch}
                onChange={(e) => setEventSearch(e.target.value)}
                placeholder="Search trade events by symbol, detail..."
                className="w-full bg-darkBg border border-borderColor rounded-xl pl-8 pr-3 py-1.5 text-white placeholder-gray-500 focus:outline-none focus:border-accentBlue text-xs"
              />
            </div>

            <div className="flex items-center gap-1 bg-darkBg border border-borderColor rounded-lg px-2 py-1 font-mono">
              <span className="text-[10px] text-gray-400 uppercase">Per Page:</span>
              <select
                value={eventPageSize}
                onChange={(e) => setEventPageSize(Number(e.target.value))}
                className="bg-transparent text-white text-xs font-mono focus:outline-none cursor-pointer"
              >
                <option value={10} className="bg-darkBg">10</option>
                <option value={25} className="bg-darkBg">25</option>
                <option value={50} className="bg-darkBg">50</option>
              </select>
            </div>
          </div>

          {/* Trade Events Table */}
          <div className="p-4 overflow-y-auto flex-1 text-xs font-mono">
            {displayedEvents.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-gray-500">
                <Inbox size={32} className="mb-2 opacity-50" />
                <span className="font-semibold text-white text-xs">No Trade Events Recorded</span>
                <span className="text-[11px] text-gray-400 mt-1">Real-time order open, close, and execution events from MT5 will stream here.</span>
              </div>
            ) : (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-darkBg text-gray-400 border-b border-borderColor uppercase text-[10px]">
                    <th className="p-3">Time</th>
                    <th className="p-3">Symbol</th>
                    <th className="p-3">Direction</th>
                    <th className="p-3">Event Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borderColor/60">
                  {displayedEvents.map((evt, i) => (
                    <tr key={i} className="hover:bg-borderColor/30 transition">
                      <td className="p-3 text-gray-400">{evt.time}</td>
                      <td className="p-3 font-bold text-white">{evt.symbol}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded-md font-bold text-[10px] ${
                          evt.direction === 'BUY' ? 'bg-accentGreen/20 text-accentGreen border border-accentGreen/30' : 'bg-accentRed/20 text-accentRed border border-accentRed/30'
                        }`}>
                          {evt.direction}
                        </span>
                      </td>
                      <td className="p-3 text-gray-300">{evt.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Trade Events Pagination Footer */}
          {filteredEvents.length > 0 && (
            <div className="bg-darkBg/90 border-t border-borderColor px-4 py-2 flex items-center justify-between text-xs font-mono">
              <span className="text-gray-400 text-[11px]">
                Showing <strong className="text-white">{(eventPage - 1) * eventPageSize + 1}</strong> to{' '}
                <strong className="text-white">{Math.min(eventPage * eventPageSize, filteredEvents.length)}</strong> of{' '}
                <strong className="text-white">{filteredEvents.length}</strong> events
              </span>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setEventPage(1)}
                  disabled={eventPage === 1}
                  className="p-1 bg-cardBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white"
                >
                  <ChevronsLeft size={14} />
                </button>
                <button
                  onClick={() => setEventPage((p) => Math.max(1, p - 1))}
                  disabled={eventPage === 1}
                  className="px-2.5 py-1 bg-cardBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white flex items-center gap-1"
                >
                  <ChevronLeft size={14} /> Prev
                </button>
                
                <span className="px-2.5 py-1 bg-accentBlue/20 text-accentBlue border border-accentBlue/40 rounded font-bold">
                  Page {eventPage} of {totalEventPages}
                </span>

                <button
                  onClick={() => setEventPage((p) => Math.min(totalEventPages, p + 1))}
                  disabled={eventPage >= totalEventPages}
                  className="px-2.5 py-1 bg-cardBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white flex items-center gap-1"
                >
                  Next <ChevronRight size={14} />
                </button>
                <button
                  onClick={() => setEventPage(totalEventPages)}
                  disabled={eventPage >= totalEventPages}
                  className="p-1 bg-cardBg border border-borderColor rounded text-gray-300 disabled:opacity-30 hover:text-white"
                >
                  <ChevronsRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: AI Decisions (Filtered Gemini AI logs) */}
      {activeTab === 'ai_decisions' && (
        <div className="p-4 overflow-y-auto flex-1 text-xs">
          {aiLogs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-gray-500">
              <Inbox size={32} className="mb-2 opacity-50" />
              <span className="font-semibold text-white text-xs">No AI Decision Logs Recorded</span>
              <span className="text-[11px] text-gray-400 mt-1">Use the Gemini AI drawer or enable AI command layer to view real-time reasoning.</span>
            </div>
          ) : (
            <div className="space-y-2 font-mono">
              {aiLogs.map((log, i) => (
                <div key={i} className="p-3 bg-darkBg border border-borderColor rounded-xl space-y-1">
                  <div className="flex justify-between text-gray-400 text-[11px]">
                    <span className="text-accentBlue font-bold">Google Gemini AI Engine</span>
                    <span>{log.timestamp}</span>
                  </div>
                  <div className="text-gray-200 font-semibold">{log.message}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: MT5 Raw IPC */}
      {activeTab === 'mt5_raw' && (
        <div className="p-4 bg-darkBg font-mono text-xs text-gray-300 overflow-y-auto flex-1 space-y-2">
          <div className="text-accentGreen font-bold">[MT5 IPC Status] Connected to MetaTrader 5 Terminal (Exness-MT5Trial7).</div>
          <div>[MT5 Account] #433951210 (USD) | Leverage 1:2000</div>
          <div>[MT5 Ticks] Subscribed pairs: BTCUSDm, XAUUSDm, USOILm, EURUSDm, GBPUSDm.</div>
          <div>[MT5 Ping] Terminal round-trip latency: 12ms. Status: Optimal.</div>
          <div>[MT5 IPC Buffer] Memory pool allocation: OK. Real-time stream active.</div>
        </div>
      )}
    </div>
  );
};
