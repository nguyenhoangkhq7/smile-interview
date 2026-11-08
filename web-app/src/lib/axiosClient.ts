import axios from 'axios';
import { useAuthStore } from '../store/authStore';
import { expireSession, getTokenExpiresAt } from './authSession';

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8081';

const axiosClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000, // 180s (3 minutes) timeout for long-running AI / Skill-Gap / Interview pipelines
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add the auth token header to requests
axiosClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token && config.headers) {
      const expiresAt = getTokenExpiresAt(token);
      if (expiresAt === null || expiresAt <= Date.now()) {
        expireSession(token);
        return Promise.reject(new axios.CanceledError('Session expired'));
      }
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// A 403 means insufficient permissions and must not log the user out.
axiosClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      const authorization = error.config?.headers?.Authorization;
      if (typeof authorization === 'string' && authorization.startsWith('Bearer ')) {
        expireSession(authorization.slice(7));
      }
    }
    return Promise.reject(error);
  }
);

export default axiosClient;
