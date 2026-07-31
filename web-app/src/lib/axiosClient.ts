import axios from 'axios';

// ----------------------------------------------------------------
// Axios instance — points at the Spring Boot matching-service
// ----------------------------------------------------------------

const axiosClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8081',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300_000, // 300 s (5 minutes)
});

// ----------------------------------------------------------------
// Request interceptor — attach JWT from localStorage
// ----------------------------------------------------------------

axiosClient.interceptors.request.use(
  (config) => {
    try {
      // Zustand persist stores data as JSON under the key 'auth-storage'
      const raw = localStorage.getItem('auth-storage');
      if (raw) {
        const parsed = JSON.parse(raw) as { state?: { token?: string } };
        const token = parsed?.state?.token;
        if (token) {
          config.headers['Authorization'] = `Bearer ${token}`;
        }
      }
    } catch {
      // If localStorage is unavailable (SSR) or JSON is malformed, proceed without token
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ----------------------------------------------------------------
// Response interceptor — handle 401 globally
// ----------------------------------------------------------------

axiosClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear stale auth data and redirect to login
      try {
        localStorage.removeItem('auth-storage');
      } catch {
        // no-op in SSR
      }
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default axiosClient;
