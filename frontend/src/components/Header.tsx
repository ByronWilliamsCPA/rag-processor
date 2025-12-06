/**
 * Application header with user authentication status.
 */

import { useAuth } from '@/hooks/useAuth';
import './Header.css';

export function Header() {
  const { user, isLoading, error, isAuthenticated, logout } = useAuth();

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-brand">
          <h1>RAG Processor</h1>
        </div>

        <div className="header-user">
          {isLoading && <span className="loading-indicator">Loading...</span>}

          {error && <span className="error-indicator">Auth Error</span>}

          {!isLoading && !error && isAuthenticated && user && (
            <div className="user-info">
              <span className="user-email">{user.email}</span>
              <button onClick={logout} className="logout-button">
                Logout
              </button>
            </div>
          )}

          {!isLoading && !error && !isAuthenticated && (
            <span className="not-authenticated">Not authenticated</span>
          )}
        </div>
      </div>
    </header>
  );
}
