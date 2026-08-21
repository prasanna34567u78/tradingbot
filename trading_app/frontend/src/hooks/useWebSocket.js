import { useEffect } from 'react';
import { useAccountStore } from '../store/accountStore';
import { usePositionsStore } from '../store/positionsStore';
import { useLogStore } from '../store/logStore';
import { useAnalyticsStore } from '../store/analyticsStore';

export const useWebSocket = () => {
  const setAccount = useAccountStore((state) => state.setAccount);
  const setBotRunning = useAccountStore((state) => state.setBotRunning);
  const setWsConnected = useAccountStore((state) => state.setWsConnected);
  const setPositions = usePositionsStore((state) => state.setPositions);
  const appendLogs = useLogStore((state) => state.appendLogs);
  
  const setEquityCurve = useAnalyticsStore((state) => state.setEquityCurve);
  const setSymbolDistribution = useAnalyticsStore((state) => state.setSymbolDistribution);
  const setActivityFeed = useAnalyticsStore((state) => state.setActivityFeed);

  useEffect(() => {
    let ws = null;
    let reconnectTimer = null;

    const connect = () => {
      ws = new WebSocket('ws://localhost:8000/ws');

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'tick') {
            if (data.account) setAccount(data.account);
            if (data.positions) setPositions(data.positions);
            if (typeof data.bot_running === 'boolean') setBotRunning(data.bot_running);
            if (data.recent_logs) appendLogs(data.recent_logs);
            if (data.equity_curve) setEquityCurve(data.equity_curve);
            if (data.symbol_distribution) setSymbolDistribution(data.symbol_distribution);
            if (data.activity_feed) setActivityFeed(data.activity_feed);
          }
        } catch (e) {
          console.error('WS JSON error:', e);
        }
      };

      ws.onerror = () => {
        setWsConnected(false);
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      if (ws) ws.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, []);
};
