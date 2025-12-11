/**
 * Authentication hook for RAG Processor.
 *
 * Fetches user info from the backend and manages auth state.
 */

import { useCallback, useEffect, useRef } from 'react';
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

  // Use ref to track abort controller for cleanup
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchUser = useCallback(async () => {
    // Abort any in-flight request
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    try {
      const response = await axios.get<User>(`${API_URL}/api/v1/user/me`, {
        withCredentials: true,
        signal: abortControllerRef.current.signal,
        timeout: 10000, // 10 second timeout
      });
      setUser(response.data);
    } catch (err) {
      // Ignore abort errors from cleanup
      if (axios.isCancel(err)) {
        return;
      }
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
  }, [setUser, setError]);

  useEffect(() => {
    fetchUser();

    return () => {
      abortControllerRef.current?.abort();
    };
  }, [fetchUser]);

  return {
    user,
    isLoading,
    error,
    isAuthenticated,
    logout,
    refetch: fetchUser,
  };
}
