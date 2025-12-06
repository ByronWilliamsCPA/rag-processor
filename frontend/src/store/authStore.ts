/**
 * Zustand store for authentication state.
 */

import { create } from 'zustand';
import type { User } from '@/types/auth';

interface AuthStore {
  // State
  user: User | null;
  isLoading: boolean;
  error: string | null;

  // Computed
  isAuthenticated: boolean;

  // Actions
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  logout: () => void;
  reset: () => void;
}

const initialState = {
  user: null,
  isLoading: true, // Start loading until we check auth
  error: null,
  isAuthenticated: false,
};

export const useAuthStore = create<AuthStore>((set) => ({
  ...initialState,

  setUser: (user) =>
    set({
      user,
      isAuthenticated: user !== null,
      isLoading: false,
      error: null,
    }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) =>
    set({
      error,
      isLoading: false,
    }),

  logout: () => {
    // Clear state
    set(initialState);
    set({ isLoading: false });

    // Redirect to Cloudflare logout
    // The logout URL will be configured via environment variable
    const logoutUrl = import.meta.env.VITE_CLOUDFLARE_LOGOUT_URL;
    if (logoutUrl) {
      window.location.href = logoutUrl;
    }
  },

  reset: () => set(initialState),
}));
