import axios from 'axios';

const getBaseURL = () => {
  if (typeof window !== 'undefined') {
    // If running in Vite development server (port 5173), proxy to FastAPI backend
    if (window.location.port === '5173') {
      return `http://${window.location.hostname}:8000`;
    }
    // In production (domain HTTPS, IP port 8000, or localhost), use same origin
    return window.location.origin;
  }
  return 'http://127.0.0.1:8000';
};

const client = axios.create({
  baseURL: getBaseURL(),
  timeout: 20000,
  headers: {
    'Content-Type': 'application/json',
  },
});

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Request Error:', error?.response || error.message);
    return Promise.reject(error);
  }
);

export default client;
