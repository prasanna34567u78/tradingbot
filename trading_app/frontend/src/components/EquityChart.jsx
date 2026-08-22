import React, { useState, useMemo } from 'react';
import { useAnalyticsStore } from '../store/analyticsStore';
import { 
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, 
  AreaChart, Area 
} from 'recharts';
import { BarChart3, LineChart, TrendingUp, Calendar } from 'lucide-react';

export const EquityChart = () => {
  const [range, setRange] = useState('1W'); // '1D', '1W', '1M', 'All'
  const [chartType, setChartType] = useState('bar'); // 'bar' or 'area'
  const equityCurve = useAnalyticsStore((state) => state.equityCurve);

  const hasData = Array.isArray(equityCurve) && equityCurve.length > 0;

  // Filter equity data based on selected time range
  const filteredData = useMemo(() => {
    if (!hasData) return [];
    if (range === 'All') return equityCurve;

    const now = Date.now();
    let cutoffMs = 0;

    if (range === '1D') cutoffMs = 24 * 60 * 60 * 1000;
    else if (range === '1W') cutoffMs = 7 * 24 * 60 * 60 * 1000;
    else if (range === '1M') cutoffMs = 30 * 24 * 60 * 60 * 1000;

    const filtered = equityCurve.filter((item) => {
      if (item.time === 'Now') return true;
      if (item.timestamp) return now - item.timestamp <= cutoffMs;
      // Fallback if timestamp isn't present
      return true;
    });

    // If filter left fewer than 2 items but we have data, show the latest slice
    if (filtered.length < 2 && equityCurve.length >= 2) {
      const sliceCount = range === '1D' ? 5 : (range === '1W' ? 15 : 30);
      return equityCurve.slice(-sliceCount);
    }

    return filtered;
  }, [equityCurve, range, hasData]);

  // Calculate dynamic Y-axis min/max
  const { minVal, maxVal } = useMemo(() => {
    if (!filteredData.length) return { minVal: 0, maxVal: 100 };
    const values = filteredData.map((d) => d.equity || 0);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.1, 5);
    return {
      minVal: Math.max(0, Math.floor(min - padding)),
      maxVal: Math.ceil(max + padding)
    };
  }, [filteredData]);

  // Bar Color Determinator
  const getBarColor = (entry) => {
    if (entry.trade === 'live' || entry.time === 'Now') return '#58a6ff'; // Accent Blue for live/current
    if (entry.trade === 'win' || (entry.pnl !== undefined && entry.pnl >= 0)) return '#00d395'; // Accent Green
    return '#f78166'; // Accent Red for loss
  };

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-[#161b22] border border-borderColor p-3 rounded-xl shadow-2xl font-mono text-xs space-y-1">
          <div className="text-gray-400 font-semibold text-[11px] flex items-center gap-1.5">
            <Calendar size={12} className="text-accentBlue" />
            {data.date ? `${data.date} ${data.time}` : data.time}
          </div>
          <div className="text-white font-bold text-sm">
            Equity: <span className="text-accentGreen">${Number(data.equity || 0).toFixed(2)}</span>
          </div>
          {data.pnl !== undefined && data.trade !== 'live' && (
            <div className={`text-[11px] font-bold ${data.pnl >= 0 ? 'text-accentGreen' : 'text-accentRed'}`}>
              P&L: {data.pnl >= 0 ? '+' : ''}${Number(data.pnl).toFixed(2)}
            </div>
          )}
          <div className="text-[10px] text-gray-500 uppercase">
            Type: {data.trade === 'live' ? 'Current Valuation' : `${data.trade} Trade`}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-cardBg border border-borderColor p-5 rounded-2xl flex flex-col h-full shadow-lg relative overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 z-10">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 size={18} className="text-accentGreen" />
            <h3 className="font-bold text-white text-sm">Portfolio Equity Curve</h3>
          </div>
          <span className="text-xs text-gray-400">Vertical bar progression & trade outcomes</span>
        </div>
        
        <div className="flex items-center gap-2 flex-wrap">
          {/* Chart Type Toggle (Bar vs Area) */}
          <div className="flex bg-darkBg p-0.5 rounded-xl border border-borderColor">
            <button
              onClick={() => setChartType('bar')}
              className={`p-1.5 rounded-lg transition ${
                chartType === 'bar' ? 'bg-accentGreen/20 text-accentGreen border border-accentGreen/40' : 'text-gray-400 hover:text-white'
              }`}
              title="Vertical Bar Chart"
            >
              <BarChart3 size={14} />
            </button>
            <button
              onClick={() => setChartType('area')}
              className={`p-1.5 rounded-lg transition ${
                chartType === 'area' ? 'bg-accentBlue/20 text-accentBlue border border-accentBlue/40' : 'text-gray-400 hover:text-white'
              }`}
              title="Area Line Chart"
            >
              <LineChart size={14} />
            </button>
          </div>

          {/* Time Range Filters */}
          <div className="flex gap-1 bg-darkBg p-1 rounded-xl border border-borderColor font-mono text-xs">
            {['1D', '1W', '1M', 'All'].map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 rounded-lg font-bold transition ${
                  range === r ? 'bg-accentBlue text-white shadow-md' : 'text-gray-400 hover:text-white'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>

      {!hasData ? (
        <div className="flex-1 flex flex-col items-center justify-center min-h-[220px] p-6 text-center bg-darkBg/40 border border-borderColor/50 rounded-xl my-2">
          <div className="p-3 bg-borderColor/40 rounded-full text-gray-500 mb-2">
            <TrendingUp size={28} />
          </div>
          <h4 className="font-semibold text-white text-xs">No Equity History Data Available</h4>
          <p className="text-[11px] text-gray-400 max-w-xs mt-1">
            Historical portfolio curve will populate automatically as trades execute on your MT5 account.
          </p>
        </div>
      ) : (
        <div className="w-full h-64 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            {chartType === 'bar' ? (
              /* Vertical Bar Chart */
              <BarChart data={filteredData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                <XAxis dataKey="time" stroke="#8b949e" tickLine={false} fontSize={10} fontStyle="mono" />
                <YAxis 
                  stroke="#8b949e" 
                  tickLine={false} 
                  domain={[minVal, maxVal]} 
                  fontSize={10} 
                  fontStyle="mono" 
                  tickFormatter={(val) => `$${val}`} 
                />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }} />
                <Bar dataKey="equity" radius={[4, 4, 0, 0]} maxBarSize={36}>
                  {filteredData.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={getBarColor(entry)}
                      stroke={entry.trade === 'win' ? '#00b37e' : (entry.trade === 'loss' ? '#e05338' : '#388bfd')}
                      strokeWidth={1}
                    />
                  ))}
                </Bar>
              </BarChart>
            ) : (
              /* Area Chart */
              <AreaChart data={filteredData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                <defs>
                  <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d395" stopOpacity={0.35}/>
                    <stop offset="95%" stopColor="#00d395" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                <XAxis dataKey="time" stroke="#8b949e" tickLine={false} fontSize={10} fontStyle="mono" />
                <YAxis stroke="#8b949e" tickLine={false} domain={[minVal, maxVal]} fontSize={10} fontStyle="mono" tickFormatter={(val) => `$${val}`} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="equity" stroke="#00d395" strokeWidth={2.5} fillOpacity={1} fill="url(#equityGrad)" />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
