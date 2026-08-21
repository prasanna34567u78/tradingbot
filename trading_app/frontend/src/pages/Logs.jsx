import React from 'react';
import { LogViewer } from '../components/LogViewer';

export const Logs = () => {
  return (
    <div className="space-y-4 pb-12">
      <div>
        <h2 className="font-bold text-white text-xl">Real-Time Activity Terminal Logs</h2>
        <span className="text-xs text-gray-400">Streamed via WebSocket with 4 dedicated inspection tabs</span>
      </div>

      <LogViewer />
    </div>
  );
};
