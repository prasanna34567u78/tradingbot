import React, { useState } from 'react';
import { useAnalyticsStore } from '../store/analyticsStore';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { TrendingUp, LineChart, AlertCircle } from 'lucide-react';

export const EquityChart = () => {
  const [range, setRange] = useState('1W');
  const equityCurve = useAnalyticsStore((state) => state.equityCurve);

  const hasData = Array.isArray(equityCurve) && equityCurve.length > 0;

  return (
    <div className="bg-cardBg border border-borderColor p-5 rounded-2xl flex flex-col h-full shadow-lg relative overflow-hidden">
      <div className="flex items-center justify-between mb-4 z-10">
        <div>
          <div className="flex items-center gap-2">
            <LineChart size={18} className="text-accentGreen" />
            <h3 className="font-bold text-white text-sm">Portfolio Equity Curve</h3>
          </div>
          <span className="text-xs text-gray-400">Live portfolio valuation progression</span>
        </div>
        
        {hasData && (
          <div className="flex gap-1 bg-darkBg p-1 rounded-xl border border-borderColor">
            {['1D', '1W', '1M', 'All'].map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 text-xs rounded-lg font-semibold transition ${
                  range === r ? 'bg-accentBlue text-white shadow-md' : 'text-gray-400 hover:text-white'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        )}
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
            <AreaChart data={equityCurve}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00d395" stopOpacity={0.35}/>
                  <stop offset="95%" stopColor="#00d395" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
              <XAxis dataKey="time" stroke="#8b949e" tickLine={false} fontSize={11} />
              <YAxis stroke="#8b949e" tickLine={false} domain={['dataMin - 10', 'dataMax + 10']} fontSize={11} tickFormatter={(val) => `$${val}`} />
              <Tooltip
                contentStyle={{ backgroundColor: '#161b22', borderColor: '#30363d', borderRadius: '12px', color: '#e6edf3', boxShadow: '0 10px 25px -5px rgba(0,0,0,0.5)' }}
                formatter={(val) => [`$${parseFloat(val).toFixed(2)}`, 'Equity']}
              />
              <Area type="monotone" dataKey="equity" stroke="#00d395" strokeWidth={2.5} fillOpacity={1} fill="url(#equityGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
