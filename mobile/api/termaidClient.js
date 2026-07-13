import axios from 'axios';
import { BASE_URL, ENDPOINTS } from './termaidConfig';
import { getTokens, saveTokens, clearTokens } from './termaidTokens';

let isRefreshing = false;
let refreshSubscribers = [];

const subscribeTokenRefresh = (cb) => {
  refreshSubscribers.push(cb);
};

const onRefreshed = (token) => {
  refreshSubscribers.map((cb) => cb(token));
  refreshSubscribers = [];
};

const client = axios.create({ baseURL: BASE_URL, timeout: 10000 });

client.interceptors.request.use(async (config) => {
  const { access } = await getTokens();
  if (access) {
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  async (err) => {
    const originalRequest = err.config;
    if (err.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(client(originalRequest));
          });
        });
      }
      originalRequest._retry = true;
      isRefreshing = true;
      try {
        const { refresh } = await getTokens();
        if (!refresh) throw new Error('No refresh token');
        const { data } = await axios.post(`${BASE_URL}${ENDPOINTS.authRefresh}`, { refresh_token: refresh });
        await saveTokens(data.access_token, data.refresh_token);
        isRefreshing = false;
        onRefreshed(data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return client(originalRequest);
      } catch (refreshErr) {
        isRefreshing = false;
        await clearTokens();
        return Promise.reject(refreshErr);
      }
    }
    // Offline backoff logic / error handling
    return Promise.reject(err);
  }
);

export default client;
