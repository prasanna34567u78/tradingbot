import client from './client';

export const getConfig = () => client.get('/api/config');
export const updateConfig = (config) => client.put('/api/config', config);

export const getMT5Symbols = () => client.get('/api/mt5/symbols');

export const getAccountInfo = () => client.get('/api/account');
export const updateAccountInfo = (accountData) => client.put('/api/account', accountData);

export const getPositions = () => client.get('/api/positions');
export const openPosition = (tradeData) => client.post('/api/positions/open', tradeData);
export const closePosition = (ticket) => client.post('/api/positions/close', { ticket });
export const partialClosePosition = (data) => client.post('/api/positions/partial-close', data);
export const modifyPosition = (modifyData) => client.post('/api/positions/modify', modifyData);

export const startBot = () => client.post('/api/bot/start');
export const stopBot = () => client.post('/api/bot/stop');
export const getBotStatus = () => client.get('/api/bot/status');

export const getHistory = () => client.get('/api/history');
export const getEquityCurve = () => client.get('/api/equity-curve');
export const getSymbolDistribution = () => client.get('/api/symbol-distribution');
export const getActivityFeed = () => client.get('/api/activity-feed');
export const getPerformance = () => client.get('/api/performance');
export const runBacktest = (backtestParams) => client.post('/api/backtest', backtestParams);
export const getBacktestStatus = (runId) => client.get(`/api/backtest/${runId}`);

export const sendAICommand = (command) => client.post('/api/ai/command', { command });
