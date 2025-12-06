/**
 * Authentication hook for RAG Processor.
 *
 * Fetches user info from the backend and manages auth state.
 */

import { useEffect } from 'react';
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import type { User } from '@/types/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Hook to manage authentication state.
 *
 * Automatically fetches user info on mount and provides
 * auth state and actions.
 *
 * @returns Auth state and actions
 */
export function useAuth() {
  const { user, isLoading, error, isAuthenticated, setUser, setError, logout } =
    useAuthStore();

  useEffect(() => {
    fetchUser();
  }, []);

  /**
   * Fetch current user from backend.
   */
  async function fetchUser() {
    try {
      const response = await axios.get<User>(`${API_URL}/api/v1/user/me`, {
        withCredentials: true,
      });
      setUser(response.data);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        if (err.response?.status === 401) {
          // Not authenticated - this is expected for unauthenticated users
          setUser(null);
        } else {
          setError(err.message || 'Failed to fetch user');
        }
      } else {
        setError('An unexpected error occurred');
      }
    }
  }

  return {
    user,
    isLoading,
    error,
    isAuthenticated,
    logout,
    refetch: fetchUser,
  };
}
