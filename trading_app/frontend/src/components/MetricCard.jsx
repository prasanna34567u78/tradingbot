import React from 'react';

export const MetricCard = ({ title, value, subtext, indicator = 'neutral', icon: Icon }) => {
  let indicatorColor = 'text-gray-100';
  if (indicator === 'green') indicatorColor = 'text-accentGreen';
  if (indicator === 'red') indicatorColor = 'text-accentRed';
  if (indicator === 'amber') indicatorColor = 'text-amber-400';

  return (
    <div className="bg-cardBg border border-borderColor p-3 sm:p-4 rounded-xl shadow-sm hover:border-borderColor/80 transition flex flex-col justify-between">
      <div className="flex items-center justify-between">
        <span className="text-[10px] sm:text-xs text-gray-400 font-medium uppercase tracking-wider truncate">{title}</span>
        {Icon && <Icon size={16} className="text-gray-500 flex-shrink-0" />}
      </div>
      <div className={`text-base sm:text-2xl font-bold mt-1.5 sm:mt-2 truncate ${indicatorColor}`}>{value}</div>
      {subtext && <div className="text-[10px] sm:text-[11px] text-gray-500 mt-1 truncate hidden sm:block">{subtext}</div>}
    </div>
  );
};
