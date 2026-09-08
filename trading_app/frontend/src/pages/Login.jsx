import React, { useState } from 'react';
import { TrendingUp, Lock, User, Eye, EyeOff, Shield } from 'lucide-react';

// ── Hardcoded credentials ────────────────────────────────────────────────────
const VALID_USERNAME = 'prasanna';
const VALID_PASSWORD = 'Prasanna@tradingbot123';

export function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Simulate brief check delay for UX
    setTimeout(() => {
      if (
        username.trim().toLowerCase() === VALID_USERNAME &&
        password === VALID_PASSWORD
      ) {
        // Store auth token in sessionStorage (clears on tab/browser close)
        sessionStorage.setItem('auth_token', btoa(`${username}:${Date.now()}`));
        sessionStorage.setItem('auth_user', username.trim().toLowerCase());
        onLoginSuccess();
      } else {
        setError('Invalid username or password. Please try again.');
        setShake(true);
        setTimeout(() => setShake(false), 600);
        setPassword('');
      }
      setLoading(false);
    }, 400);
  };

  return (
    <div className="min-h-screen bg-darkBg flex items-center justify-center p-4">
      {/* Background grid effect */}
      <div
        className="fixed inset-0 opacity-5 pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(rgba(99,102,241,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.3) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div
        className={`w-full max-w-md transition-all duration-300 ${shake ? 'animate-[shake_0.5s_ease-in-out]' : ''}`}
        style={shake ? { animation: 'shake 0.5s ease-in-out' } : {}}
      >
        {/* Logo / Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-accentBlue to-purple-600 mb-4 shadow-lg shadow-blue-500/30">
            <TrendingUp size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            Trading Bot
          </h1>
          <p className="text-gray-400 mt-1 text-sm">
            Secure Access — Authorized Users Only
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-cardBg border border-borderColor rounded-2xl shadow-2xl shadow-black/40 p-8">
          {/* Security badge */}
          <div className="flex items-center gap-2 mb-6 px-3 py-2 bg-green-500/10 border border-green-500/20 rounded-lg">
            <Shield size={14} className="text-green-400 shrink-0" />
            <span className="text-green-400 text-xs font-medium">
              Protected with session authentication
            </span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Username
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
                  <User size={16} />
                </span>
                <input
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); setError(''); }}
                  placeholder="Enter username"
                  required
                  className="w-full pl-10 pr-4 py-3 bg-darkBg border border-borderColor rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-accentBlue focus:ring-1 focus:ring-accentBlue transition"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
                  <Lock size={16} />
                </span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(''); }}
                  placeholder="Enter password"
                  required
                  className="w-full pl-10 pr-12 py-3 bg-darkBg border border-borderColor rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-accentBlue focus:ring-1 focus:ring-accentBlue transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Error message */}
            {error && (
              <div className="flex items-center gap-2 px-3 py-2.5 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                <span className="shrink-0">⚠</span>
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full py-3 mt-1 bg-gradient-to-r from-accentBlue to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  Verifying...
                </>
              ) : (
                <>
                  <Lock size={16} />
                  Sign In
                </>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-600 text-xs mt-6">
          &copy; {new Date().getFullYear()} Trading Bot &mdash; Private Access Only
        </p>
      </div>

      {/* Shake animation keyframes */}
      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          15%       { transform: translateX(-8px); }
          30%       { transform: translateX(8px); }
          45%       { transform: translateX(-6px); }
          60%       { transform: translateX(6px); }
          75%       { transform: translateX(-4px); }
          90%       { transform: translateX(4px); }
        }
      `}</style>
    </div>
  );
}

export default Login;
