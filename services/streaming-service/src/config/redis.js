import { createClient } from 'redis';
import dotenv from 'dotenv';

dotenv.config();

let redisClient;

if (process.env.NODE_ENV === 'test') {
  const store = new Map();
  redisClient = {
    isOpen: true,
    connect: async () => {},
    on: () => {},
    get: async (key) => {
      return store.get(key) || null;
    },
    set: async (key, val) => {
      store.set(key, String(val));
      return 'OK';
    },
    hSet: async (key, fieldOrObj, val) => {
      if (!store.has(key)) {
        store.set(key, {});
      }
      const hash = store.get(key);
      if (typeof fieldOrObj === 'object' && fieldOrObj !== null) {
        for (const [k, v] of Object.entries(fieldOrObj)) {
          hash[k] = String(v);
        }
      } else {
        hash[fieldOrObj] = String(val);
      }
      return 1;
    },
    hGet: async (key, field) => {
      const hash = store.get(key);
      if (!hash || typeof hash !== 'object') return null;
      return hash[field] || null;
    },
    hGetAll: async (key) => {
      const hash = store.get(key);
      if (!hash || typeof hash !== 'object') return {};
      return { ...hash };
    },
    sAdd: async (key, member) => {
      if (!store.has(key)) {
        store.set(key, new Set());
      }
      const set = store.get(key);
      if (set instanceof Set) {
        set.add(String(member));
        return 1;
      }
      return 0;
    },
    sRem: async (key, member) => {
      const set = store.get(key);
      if (set instanceof Set) {
        const deleted = set.delete(String(member));
        return deleted ? 1 : 0;
      }
      return 0;
    },
    del: async (key) => {
      const deleted = store.delete(key);
      return deleted ? 1 : 0;
    }
  };
} else {
  redisClient = createClient({
    url: process.env.REDIS_URL || 'redis://localhost:6379'
  });

  redisClient.on('connect', () => {
    console.log('Redis client connected successfully');
  });

  redisClient.on('error', (err) => {
    console.error('Redis client connection error:', err);
  });
}

export const connectRedis = async () => {
  if (redisClient.connect && !redisClient.isOpen) {
    await redisClient.connect();
  }
};

export default redisClient;
