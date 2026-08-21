import React from 'react';
import { useConfigStore } from '../store/configStore';
import { WeightSliders } from '../components/WeightSliders';
import { Bot, Cpu, Sparkles, Key, Sliders, CheckCircle } from 'lucide-react';

export const AISettings = () => {
  const config = useConfigStore((state) => state.config);
  const updateField = useConfigStore((state) => state.updateField);

  if (!config) return null;

  const aiEngine = config.GEMINI_API_KEY ? 'gemini' : (config.AI_SETTINGS?.enable_openai ? 'openai' : 'randomforest');
  const confidence = config.AI_SETTINGS?.confidence_threshold ?? 0.55;

  const getGaugeColor = (val) => {
    if (val < 0.5) return 'text-accentRed border-accentRed/30 bg-accentRed/10';
    if (val <= 0.6) return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    return 'text-accentGreen border-accentGreen/30 bg-accentGreen/10';
  };

  return (
    <div className="space-y-8 pb-12">
      <div>
        <h2 className="font-bold text-white text-xl">AI Intelligence & Model Settings</h2>
        <span className="text-xs text-gray-400">Configure AI decision engines, confidence thresholds, and feature weights</span>
      </div>

      {/* AI Engine Selector Tabs */}
      <div className="bg-cardBg border border-borderColor p-4 rounded-2xl space-y-3">
        <h3 className="font-bold text-white text-sm flex items-center gap-2">
          <Bot size={18} className="text-blue-400" /> Active AI Analysis Engine
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { id: 'gemini', label: 'Google Gemini AI CLI', icon: Sparkles, desc: 'Gemini 1.5 Pro natural language & market reasoning engine' },
            { id: 'openai', label: 'OpenAI GPT-4o API', icon: Bot, desc: 'OpenAI GPT-4o-mini structured analysis engine' },
            { id: 'randomforest', label: 'Local RandomForest ML', icon: Cpu, desc: 'Offline 14-Feature ML classification model' },
          ].map((engine) => {
            const Icon = engine.icon;
            const isSelected = (engine.id === 'gemini' && config.GEMINI_API_KEY) ||
              (engine.id === 'openai' && !config.GEMINI_API_KEY && config.AI_SETTINGS?.enable_openai) ||
              (engine.id === 'randomforest' && !config.GEMINI_API_KEY && !config.AI_SETTINGS?.enable_openai);

            return (
              <div
                key={engine.id}
                onClick={() => {
                  if (engine.id === 'gemini') {
                    updateField('GEMINI_API_KEY', 'AIzaSy_demo_gemini_key');
                  } else if (engine.id === 'openai') {
                    updateField('GEMINI_API_KEY', '');
                    updateField('AI_SETTINGS.enable_openai', true);
                  } else {
                    updateField('GEMINI_API_KEY', '');
                    updateField('AI_SETTINGS.enable_openai', false);
                  }
                }}
                className={`p-4 rounded-xl border cursor-pointer transition ${
                  isSelected
                    ? 'bg-blue-600/10 border-blue-500 text-white shadow-md'
                    : 'bg-darkBg border-borderColor/60 text-gray-400 hover:border-borderColor'
                }`}
              >
                <div className="flex items-center gap-2 font-bold text-sm text-white mb-1">
                  <Icon size={16} className="text-blue-400" /> {engine.label}
                </div>
                <div className="text-xs text-gray-400">{engine.desc}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Gemini CLI Specific Panel */}
      {config.GEMINI_API_KEY && (
        <div className="bg-cardBg border border-blue-500/30 p-5 rounded-2xl space-y-4 text-xs">
          <h3 className="font-bold text-blue-400 text-sm flex items-center gap-2">
            <Sparkles size={16} /> Gemini AI CLI Configuration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-gray-300 font-semibold mb-1">Gemini API Key</label>
              <div className="relative">
                <input
                  type="password"
                  value={config.GEMINI_API_KEY || ''}
                  onChange={(e) => updateField('GEMINI_API_KEY', e.target.value)}
                  className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-gray-300 font-semibold mb-1">Gemini Model Variant</label>
              <select
                value={config.GEMINI_MODEL || 'gemini-1.5-pro'}
                onChange={(e) => updateField('GEMINI_MODEL', e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-xl px-3 py-2 text-white"
              >
                <option value="gemini-1.5-pro">gemini-1.5-pro (High Precision)</option>
                <option value="gemini-1.5-flash">gemini-1.5-flash (Ultra Fast)</option>
                <option value="gemini-pro">gemini-pro (Legacy)</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* OpenAI Specific Panel */}
      {!config.GEMINI_API_KEY && config.AI_SETTINGS?.enable_openai && (
        <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-4 text-xs">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <Key size={16} className="text-accentBlue" /> OpenAI API Options
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-gray-300 mb-1">Model</label>
              <select
                value={config.OPENAI_MODEL || 'gpt-4o-mini'}
                onChange={(e) => updateField('OPENAI_MODEL', e.target.value)}
                className="w-full bg-darkBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white"
              >
                <option value="gpt-4o-mini">gpt-4o-mini</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="gpt-4-turbo">gpt-4-turbo</option>
              </select>
            </div>
            <div>
              <label className="block text-gray-300 mb-1">Max Tokens</label>
              <input
                type="number"
                value={config.OPENAI_MAX_TOKENS || 500}
                onChange={(e) => updateField('OPENAI_MAX_TOKENS', parseInt(e.target.value))}
                className="w-full bg-darkBg border border-borderColor rounded-lg px-2.5 py-1.5 text-white"
              />
            </div>
            <div>
              <label className="block text-gray-300 mb-1">Temperature: {config.OPENAI_TEMPERATURE}</label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={config.OPENAI_TEMPERATURE || 0.3}
                onChange={(e) => updateField('OPENAI_TEMPERATURE', parseFloat(e.target.value))}
                className="w-full accent-accentBlue"
              />
            </div>
          </div>
        </div>
      )}

      {/* RandomForest ML Panel */}
      {!config.GEMINI_API_KEY && !config.AI_SETTINGS?.enable_openai && (
        <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-3 text-xs">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <Cpu size={16} className="text-purple-400" /> RandomForest Local ML Model
          </h3>
          <p className="text-gray-400">Offline classifier trained on 14 technical features (SMC, Orderblocks, FVG, ATR, Volatility).</p>
          <div className="p-3 bg-darkBg rounded-xl border border-borderColor font-mono text-gray-300">
            Model path: models/randomforest_trading_model.pkl (Status: Trained & Loaded)
          </div>
        </div>
      )}

      {/* AI Confidence Threshold & Gauge */}
      <div className="bg-cardBg border border-borderColor p-5 rounded-2xl space-y-4 text-xs">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <Sliders size={16} className="text-accentBlue" /> AI Confidence Threshold
          </h3>
          <div className={`px-3 py-1 rounded-full border text-xs font-bold ${getGaugeColor(confidence)}`}>
            Current Threshold: {(confidence * 100).toFixed(0)}%
          </div>
        </div>

        <div>
          <input
            type="range"
            min="0.50"
            max="0.95"
            step="0.01"
            value={confidence}
            onChange={(e) => updateField('AI_SETTINGS.confidence_threshold', parseFloat(e.target.value))}
            className="w-full accent-accentBlue"
          />
          <div className="flex justify-between text-[11px] text-gray-500 mt-1 font-mono">
            <span>50% (High risk)</span>
            <span>65% (Balanced)</span>
            <span>95% (Strict)</span>
          </div>
        </div>
      </div>

      {/* AI Weights Sliders */}
      <WeightSliders
        weights={config.AI_SETTINGS}
        onChange={updateField}
      />
    </div>
  );
};
