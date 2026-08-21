import axios from 'axios';

const getBaseURL = () => {
  if (typeof window !== 'undefined' && window.location.hostname) {
    return `http://${window.location.hostname}:8000`;
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
