import React from 'react';

export const MetricCard = ({ title, value, subtext, indicator = 'neutral', icon: Icon }) => {
  let indicatorColor = 'text-gray-200';
  if (indicator === 'green') indicatorColor = 'text-accentGreen';
  if (indicator === 'red') indicatorColor = 'text-accentRed';
  if (indicator === 'amber') indicatorColor = 'text-amber-400';

  return (
    <div className="bg-cardBg border border-borderColor p-4 rounded-xl shadow-sm hover:border-borderColor/80 transition">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">{title}</span>
        {Icon && <Icon size={18} className="text-gray-500" />}
      </div>
      <div className={`text-2xl font-bold mt-2 ${indicatorColor}`}>{value}</div>
      {subtext && <div className="text-[11px] text-gray-500 mt-1">{subtext}</div>}
    </div>
  );
};
