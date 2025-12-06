/**
 * Authentication types for RAG Processor frontend.
 */

/**
 * User information from the backend.
 */
export interface User {
  email: string;
  user_id: string | null;
  groups: string[];
}

/**
 * Authentication state.
 */
export interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;
}
