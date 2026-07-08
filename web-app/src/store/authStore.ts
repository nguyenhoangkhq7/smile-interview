import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

// ----------------------------------------------------------------
// Types
// ----------------------------------------------------------------

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  phoneNumber: string | null;
  avatarUrl: string | null;
  defaultResumeId: string | null;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;

  // Actions
  login: (user: User, token: string) => void;
  updateUser: (partial: Partial<User>) => void;
  logout: () => void;
}

// ----------------------------------------------------------------
// Store
// ----------------------------------------------------------------

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      /**
       * Called after a successful /api/auth/login or /api/auth/register.
       * Stores the user profile and JWT in the Zustand state (and localStorage).
       */
      login: (user: User, token: string) =>
        set({ user, token, isAuthenticated: true }),

      /**
       * Partially updates the stored user profile (e.g. after a profile edit).
       * Merges the provided fields into the existing user object.
       */
      updateUser: (partial: Partial<User>) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...partial } : state.user,
        })),

      /**
       * Clears all auth state and removes the persisted entry from localStorage.
       */
      logout: () =>
        set({ user: null, token: null, isAuthenticated: false }),
    }),
    {
      name: 'auth-storage',                    // localStorage key
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
