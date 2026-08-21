import React from 'react';
import { AlertCircle } from 'lucide-react';

export const WeightSliders = ({ weights, onChange }) => {
  const tech = weights?.technical_analysis_weight ?? 0.6;
  const mkt = weights?.market_condition_weight ?? 0.3;
  const sent = weights?.sentiment_analysis_weight ?? 0.1;

  const total = Number((tech + mkt + sent).toFixed(2));
  const isValid = Math.abs(total - 1.0) < 0.01;

  const handleTechChange = (val) => {
    const remain = Math.max(0, 1.0 - val);
    const ratio = mkt + sent > 0 ? mkt / (mkt + sent) : 0.5;
    const newMkt = Number((remain * ratio).toFixed(2));
    const newSent = Number((remain * (1 - ratio)).toFixed(2));
    onChange('AI_SETTINGS.technical_analysis_weight', val);
    onChange('AI_SETTINGS.market_condition_weight', newMkt);
    onChange('AI_SETTINGS.sentiment_analysis_weight', newSent);
  };

  return (
    <div className="bg-cardBg border border-borderColor p-4 rounded-xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="font-semibold text-white text-sm">AI Confluence Analysis Weights</h4>
          <span className="text-xs text-gray-400">Sliders dynamically rebalance to sum to 1.0</span>
        </div>
        <div className={`px-2.5 py-1 rounded text-xs font-semibold flex items-center gap-1 border ${
          isValid ? 'bg-accentGreen/10 text-accentGreen border-accentGreen/30' : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
        }`}>
          {!isValid && <AlertCircle size={14} />}
          Total Sum: {total.toFixed(2)} / 1.00
        </div>
      </div>

      <div className="space-y-3 text-xs">
        <div>
          <div className="flex justify-between text-gray-300 mb-1">
            <span>Technical Analysis Weight</span>
            <span className="font-bold text-accentBlue">{(tech * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0.0"
            max="1.0"
            step="0.05"
            value={tech}
            onChange={(e) => handleTechChange(parseFloat(e.target.value))}
            className="w-full accent-accentBlue"
          />
        </div>

        <div>
          <div className="flex justify-between text-gray-300 mb-1">
            <span>Market Condition Weight</span>
            <span className="font-bold text-purple-400">{(mkt * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0.0"
            max="1.0"
            step="0.05"
            value={mkt}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              const remain = Math.max(0, 1.0 - val);
              onChange('AI_SETTINGS.market_condition_weight', val);
              onChange('AI_SETTINGS.technical_analysis_weight', Number((remain * 0.7).toFixed(2)));
              onChange('AI_SETTINGS.sentiment_analysis_weight', Number((remain * 0.3).toFixed(2)));
            }}
            className="w-full accent-purple-400"
          />
        </div>

        <div>
          <div className="flex justify-between text-gray-300 mb-1">
            <span>Sentiment Analysis Weight</span>
            <span className="font-bold text-emerald-400">{(sent * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0.0"
            max="1.0"
            step="0.05"
            value={sent}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              const remain = Math.max(0, 1.0 - val);
              onChange('AI_SETTINGS.sentiment_analysis_weight', val);
              onChange('AI_SETTINGS.technical_analysis_weight', Number((remain * 0.7).toFixed(2)));
              onChange('AI_SETTINGS.market_condition_weight', Number((remain * 0.3).toFixed(2)));
            }}
            className="w-full accent-emerald-400"
          />
        </div>
      </div>
    </div>
  );
};
