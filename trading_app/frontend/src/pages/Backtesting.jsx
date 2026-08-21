import React, { useState } from 'react';
import { runBacktest, getBacktestStatus } from '../api/tradingApi';
import { useConfigStore } from '../store/configStore';
import { Play, Download, BarChart2, Database, Cpu, AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from 'recharts';

export const Backtesting = () => {
  const config = useConfigStore((state) => state.config);

  // Pull symbols from config or fallback defaults
  const configSymbols = config?.SYMBOLS
    ? Object.entries(config.SYMBOLS)
        .filter(([, d]) => d.enabled)
        .map(([s]) => s)
    : [];
  const allSymbols = ['BTCUSDm', 'XAUUSDm', 'USOILm', 'EURUSDm', 'GBPUSDm', 'USDJPYm', 'ETHUSDm'];

  const [strategy, setStrategy] = useState(config?.STRATEGY_MODE || 'mcp_enhanced');
  const [symbol, setSymbol] = useState(configSymbols[0] || 'BTCUSDm');
  const [timeframe, setTimeframe] = useState('15m');
  const [startDate, setStartDate] = useState('2026-07-01');
  const [endDate, setEndDate] = useState('2026-08-01');
  const [initialBalance, setInitialBalance] = useState(10000);
  const [lots, setLots] = useState(0.05);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [results, setResults] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState('Initializing...');

  const progressLabels = [
    'Connecting to MT5 data feed...',
    'Fetching historical candles...',
    strategy === 'crypto_vpp_v2'
      ? 'Computing Volume Profile POC/VAH/VAL + ADX Regime...'
      : 'Computing EMA / RSI / ATR indicators...',
    strategy === 'crypto_vpp_v2'
      ? 'Scoring entries (Liquidity Sweep + Market Structure)...'
      : 'Simulating strategy on candle data...',
    'Calculating Walk-Forward & Monte Carlo metrics...',
  ];

  const handleRunBacktest = async () => {
    setLoading(true);
    setErrorMsg('');
    setResults(null);
    setProgress(5);
    setProgressLabel(progressLabels[0]);

    try {
      const payload = {
        strategy: strategy || 'mcp_enhanced',
        symbol: symbol || 'BTCUSDm',
        timeframe: timeframe || '15m',
        start_date: startDate || '2026-07-01',
        end_date: endDate || '2026-08-01',
        initial_balance: parseFloat(initialBalance) || 10000.0,
        lots: parseFloat(lots) || 0.05,
      };

      const startRes = await runBacktest(payload);
      if (!startRes || !startRes.run_id) {
        throw new Error('Invalid response from backtest engine');
      }

      const runId = startRes.run_id;
      let labelIdx = 1;

      const interval = setInterval(async () => {
        try {
          const statusRes = await getBacktestStatus(runId);
          if (statusRes && typeof statusRes.progress === 'number') {
            setProgress(statusRes.progress);
            if (labelIdx < progressLabels.length && statusRes.progress >= labelIdx * 20) {
              setProgressLabel(progressLabels[labelIdx]);
              labelIdx++;
            }
          }
          if (statusRes && statusRes.status === 'completed') {
            clearInterval(interval);
            setResults(statusRes);
            setProgress(100);
            setProgressLabel('Complete!');
            setLoading(false);
          }
        } catch (e) {
          clearInterval(interval);
          setLoading(false);
          setErrorMsg('Error fetching backtest results. Check that the backend server is running.');
        }
      }, 300);
    } catch (e) {
      console.error('Backtest launch error:', e);
      setErrorMsg('Failed to launch backtest. Please ensure backend server is running on port 8000.');
      setLoading(false);
    }
  };

  const handleExportCSV = () => {
    if (!results?.trades) return;
    const headers = 'ID,Entry Date,Exit Date,Symbol,Direction,Entry Price,Exit Price,Lots,Profit\n';
    const rows = results.trades
      .map((t) => `${t.id},${t.entry_date},${t.exit_date},${t.symbol},${t.direction},${t.entry_price},${t.exit_price},${t.lots},${t.profit}`)
      .join('\n');
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_${symbol}_${strategy}_${startDate}.csv`;
    a.click();
  };

  const dataSource = results?.metrics?.data_source;
  const isMT5Real = dataSource === 'mt5_real';
  const isSynthetic = dataSource === 'synthetic';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 pb-12">
      {/* Left Panel — Parameters (4 cols) */}
      <div className="lg:col-span-4 bg-cardBg border border-borderColor p-5 rounded-2xl space-y-4 text-xs h-fit shadow-xl">
        <div className="flex items-center justify-between border-b border-borderColor pb-3">
          <h3 className="font-bold text-white text-base">Backtest Parameters</h3>
          <span className="text-[10px] text-gray-500 font-mono bg-darkBg px-2 py-1 rounded-lg border border-borderColor">
            EMA × RSI × ATR
          </span>
        </div>

        {errorMsg && (
          <div className="p-3 bg-accentRed/10 border border-accentRed/30 text-accentRed rounded-xl text-xs flex items-center gap-2">
            <AlertTriangle size={16} /> {errorMsg}
          </div>
        )}

        {/* Strategy */}
        <div>
          <label className="block text-gray-300 font-semibold mb-1">Strategy Mode</label>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white focus:border-accentBlue outline-none font-bold"
          >
            <option value="pde">PDE Strategy (Premium/Discount/Equilibrium)</option>
            <option value="crypto_vpp_v2">⚡ BTC Improved v2 (VPP + Regime + Score) — NEW</option>
            <option value="crypto_vpp">Crypto Volume Profile + EMA (BTC/Crypto)</option>
            <option value="mcp_enhanced">MCP Enhanced Strategy</option>
            <option value="standard_ai">Standard AI (Multi-TF SMC)</option>
            <option value="scalping">Scalping Mode (1M/5M)</option>
          </select>
        </div>

        {/* Symbol — includes config symbols at top */}
        <div>
          <label className="block text-gray-300 font-semibold mb-1">
            Target Symbol
            {configSymbols.length > 0 && (
              <span className="ml-2 text-[10px] text-accentBlue font-normal">({configSymbols.length} from config)</span>
            )}
          </label>
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-bold focus:border-accentBlue outline-none"
          >
            {configSymbols.length > 0 && (
              <optgroup label="— From Your Config —">
                {configSymbols.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </optgroup>
            )}
            <optgroup label="— All Symbols —">
              {allSymbols.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </optgroup>
          </select>
        </div>

        {/* Timeframe */}
        <div>
          <label className="block text-gray-300 font-semibold mb-1">Timeframe</label>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white focus:border-accentBlue outline-none"
          >
            <option value="1m">1 minute (Scalping)</option>
            <option value="5m">5 minutes</option>
            <option value="15m">15 minutes (Standard)</option>
            <option value="1h">1 hour</option>
          </select>
        </div>

        {/* Date Range */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-gray-300 font-semibold mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-darkBg border border-borderColor rounded-xl px-2.5 py-1.5 text-white focus:border-accentBlue outline-none"
            />
          </div>
          <div>
            <label className="block text-gray-300 font-semibold mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-darkBg border border-borderColor rounded-xl px-2.5 py-1.5 text-white focus:border-accentBlue outline-none"
            />
          </div>
        </div>

        {/* Initial Balance & Lots */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-gray-300 font-semibold mb-1">Initial Balance ($)</label>
            <input
              type="number"
              value={initialBalance}
              onChange={(e) => setInitialBalance(e.target.value)}
              className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono focus:border-accentBlue outline-none"
            />
          </div>
          <div>
            <label className="block text-gray-300 font-semibold mb-1">Lot Size</label>
            <input
              type="number"
              step="0.01"
              value={lots}
              onChange={(e) => setLots(e.target.value)}
              className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono focus:border-accentBlue outline-none"
            />
          </div>
        </div>

        {/* Progress */}
        <div className="pt-2">
          {loading && (
            <div className="mb-3 space-y-1.5">
              <div className="flex justify-between text-gray-400">
                <span className="font-mono text-[11px]">{progressLabel}</span>
                <span className="font-mono font-bold text-accentBlue">{progress}%</span>
              </div>
              <div className="w-full bg-darkBg h-2.5 rounded-full overflow-hidden border border-borderColor">
                <div
                  className="bg-gradient-to-r from-accentBlue to-purple-500 h-full transition-all duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          <button
            onClick={handleRunBacktest}
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-accentBlue to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-bold rounded-xl transition flex items-center justify-center gap-2 shadow-lg text-sm border border-blue-400/30"
          >
            {loading ? (
              <span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Play size={16} />
            )}
            {loading ? 'Running Backtest...' : 'Run Backtest'}
          </button>

          <p className="text-center text-[10px] text-gray-500 mt-2">
            Uses real MT5 data when connected, synthetic fallback otherwise
          </p>
        </div>
      </div>

      {/* Right Panel — Results (8 cols) */}
      <div className="lg:col-span-8 space-y-5">
        {results ? (
          <>
            {/* Data Source Badge */}
            <div className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border text-xs font-semibold ${
              isMT5Real
                ? 'bg-accentGreen/10 border-accentGreen/30 text-accentGreen'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
            }`}>
              {isMT5Real ? <Database size={14} /> : <Cpu size={14} />}
              {isMT5Real
                ? `Real MT5 Historical Data — ${symbol} (${timeframe}) | ${startDate} → ${endDate}`
                : `Synthetic Engine — ${symbol} (${timeframe}) | Deterministic simulation for ${startDate} → ${endDate} (MT5 not connected)`}
            </div>

            {/* Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                {
                  label: 'Total P&L',
                  value: `${results.metrics.total_profit >= 0 ? '+' : ''}$${results.metrics.total_profit}`,
                  color: results.metrics.total_profit >= 0 ? 'text-accentGreen' : 'text-accentRed',
                  bg: results.metrics.total_profit >= 0 ? 'border-accentGreen/20' : 'border-accentRed/20',
                },
                { label: 'Win Rate', value: `${results.metrics.win_rate}%`, color: 'text-white', bg: '' },
                { label: 'Profit Factor', value: results.metrics.profit_factor, color: results.metrics.profit_factor >= 1.3 ? 'text-accentGreen' : results.metrics.profit_factor >= 1.0 ? 'text-accentBlue' : 'text-accentRed', bg: '' },
                { label: 'Max Drawdown', value: `-${results.metrics.max_drawdown}%`, color: 'text-accentRed', bg: '' },
                { label: 'Sharpe Ratio', value: results.metrics.sharpe_ratio, color: results.metrics.sharpe_ratio >= 1.0 ? 'text-accentGreen' : 'text-purple-400', bg: '' },
                { label: 'Total Trades', value: results.metrics.total_trades, color: 'text-white', bg: '' },
                ...(strategy === 'crypto_vpp_v2' && results.metrics.sortino_ratio !== undefined ? [
                  { label: 'Sortino Ratio', value: results.metrics.sortino_ratio ?? '—', color: 'text-cyan-400', bg: '' },
                  { label: 'Calmar Ratio', value: results.metrics.calmar_ratio ?? '—', color: 'text-amber-400', bg: '' },
                  { label: 'Expectancy/Trade', value: results.metrics.expectancy_usd != null ? `$${results.metrics.expectancy_usd}` : '—', color: 'text-accentGreen', bg: '' },
                ] : []),
              ].map((m) => (
                <div key={m.label} className={`bg-cardBg border ${m.bg || 'border-borderColor'} p-4 rounded-xl shadow`}>
                  <span className="text-[10px] text-gray-400 uppercase block mb-1">{m.label}</span>
                  <span className={`text-xl font-bold ${m.color}`}>{m.value}</span>
                </div>
              ))}
            </div>

            {/* Equity Curve */}
            <div className="bg-cardBg border border-borderColor p-5 rounded-2xl shadow-lg">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-semibold text-white text-xs">Equity Curve</h4>
                <span className="text-[10px] text-gray-500 font-mono">{results.equity_curve.length} data points</span>
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={results.equity_curve}>
                    <defs>
                      <linearGradient id="eqGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00d395" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00d395" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                    <XAxis dataKey="date" stroke="#8b949e" fontSize={9} tick={{ fill: '#8b949e' }} />
                    <YAxis stroke="#8b949e" fontSize={9} tick={{ fill: '#8b949e' }} domain={['dataMin - 100', 'dataMax + 100']} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#161b22', borderColor: '#30363d', color: '#fff', fontSize: 11 }}
                      formatter={(v) => [`$${v}`, 'Equity']}
                    />
                    <ReferenceLine y={initialBalance} stroke="#8b949e" strokeDasharray="4 4" />
                    <Area type="monotone" dataKey="equity" stroke="#00d395" fill="url(#eqGradient)" strokeWidth={2.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Trade History */}
            <div className="bg-cardBg border border-borderColor rounded-2xl overflow-hidden shadow-lg">
              <div className="p-4 border-b border-borderColor flex items-center justify-between">
                <h4 className="font-semibold text-white text-xs">
                  Trade History
                  <span className="ml-2 px-2 py-0.5 rounded-full bg-accentBlue/20 text-accentBlue text-[10px]">
                    {results.trades.length} trades
                  </span>
                </h4>
                <button
                  onClick={handleExportCSV}
                  className="px-3 py-1.5 bg-accentBlue hover:bg-blue-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition"
                >
                  <Download size={13} /> Export CSV
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-left text-xs border-collapse font-mono">
                  <thead>
                    <tr className="bg-darkBg text-gray-400 uppercase border-b border-borderColor text-[10px] sticky top-0">
                      <th className="p-3">#</th>
                      <th className="p-3">Entry</th>
                      <th className="p-3">Exit</th>
                      <th className="p-3">Type</th>
                      <th className="p-3">Entry $</th>
                      <th className="p-3">Exit $</th>
                      <th className="p-3">Lots</th>
                      <th className="p-3">P&L</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-borderColor/60">
                    {results.trades.map((t) => (
                      <tr key={t.id} className="hover:bg-borderColor/30 transition">
                        <td className="p-3 text-gray-500">#{t.id}</td>
                        <td className="p-3 text-gray-300">{t.entry_date}</td>
                        <td className="p-3 text-gray-400">{t.exit_date}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                            t.direction === 'BUY'
                              ? 'text-accentGreen bg-accentGreen/10 border border-accentGreen/30'
                              : 'text-accentRed bg-accentRed/10 border border-accentRed/30'
                          }`}>
                            {t.direction}
                          </span>
                        </td>
                        <td className="p-3 text-gray-300">{t.entry_price}</td>
                        <td className="p-3 text-gray-300">{t.exit_price}</td>
                        <td className="p-3 text-gray-400">{t.lots}</td>
                        <td className={`p-3 font-bold ${t.profit >= 0 ? 'text-accentGreen' : 'text-accentRed'}`}>
                          {t.profit >= 0 ? `+$${t.profit}` : `-$${Math.abs(t.profit)}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        ) : loading ? (
          <div className="bg-cardBg border border-borderColor p-12 rounded-2xl text-center space-y-6 shadow-xl flex flex-col items-center justify-center min-h-[420px]">
            <div className="relative">
              <div className="w-20 h-20 border-4 border-accentBlue/20 border-t-accentBlue rounded-full animate-spin"></div>
              <div className="absolute inset-0 flex items-center justify-center font-mono font-bold text-sm text-accentBlue">
                {progress}%
              </div>
            </div>
            <div className="space-y-2 max-w-md">
              <h4 className="font-bold text-white text-base">Running Strategy Backtest...</h4>
              <p className="text-xs text-accentBlue font-mono">{progressLabel}</p>
              <p className="text-[11px] text-gray-400">
                Simulating {strategy.toUpperCase()} on {symbol} ({timeframe}) from {startDate} to {endDate}.
              </p>
            </div>
            <div className="w-full max-w-xs bg-darkBg h-2.5 rounded-full overflow-hidden border border-borderColor">
              <div
                className="bg-gradient-to-r from-accentBlue via-purple-500 to-accentGreen h-full transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        ) : (
          <div className="bg-cardBg border border-borderColor p-12 rounded-2xl text-center space-y-4 shadow-lg min-h-[420px] flex flex-col items-center justify-center">
            <BarChart2 size={52} className="mx-auto text-gray-600" />
            <div>
              <h4 className="font-bold text-white text-base">No Backtest Results Yet</h4>
              <p className="text-xs text-gray-400 max-w-sm mx-auto mt-2">
                Select <strong>PDE Strategy</strong>, choose <strong>XAUUSDm (Gold)</strong> or <strong>BTCUSDm</strong>, and click <strong>Run Backtest</strong> to simulate historical performance with instant charts.
              </p>
            </div>
            <div className="flex items-center justify-center gap-6 text-[11px] text-gray-500 pt-2">
              <div className="flex items-center gap-1.5">
                <Database size={12} className="text-accentGreen" />
                <span>Real MT5 data when connected</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Cpu size={12} className="text-amber-400" />
                <span>Synthetic fallback otherwise</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
