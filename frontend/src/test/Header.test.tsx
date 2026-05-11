import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Header } from '@/components/Header';
import * as useAuthModule from '@/hooks/useAuth';

// Mock the useAuth hook
vi.mock('@/hooks/useAuth');

describe('Header', () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the application title', () => {
    (useAuthModule.useAuth as Mock).mockReturnValue({
      user: null,
      isLoading: false,
      error: null,
      isAuthenticated: false,
      logout: mockLogout,
    });

    render(<Header />);
    expect(screen.getByText('RAG Processor')).toBeInTheDocument();
  });

  it('shows loading indicator when loading', () => {
    (useAuthModule.useAuth as Mock).mockReturnValue({
      user: null,
      isLoading: true,
      error: null,
      isAuthenticated: false,
      logout: mockLogout,
    });

    render(<Header />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('shows error indicator when there is an auth error', () => {
    (useAuthModule.useAuth as Mock).mockReturnValue({
      user: null,
      isLoading: false,
      error: 'Auth failed',
      isAuthenticated: false,
      logout: mockLogout,
    });

    render(<Header />);
    expect(screen.getByText('Auth Error')).toBeInTheDocument();
  });

  it('shows user email and logout button when authenticated', () => {
    (useAuthModule.useAuth as Mock).mockReturnValue({
      user: { email: 'test@example.com', user_id: 'user-123' },
      isLoading: false,
      error: null,
      isAuthenticated: true,
      logout: mockLogout,
    });

    render(<Header />);
    expect(screen.getByText('test@example.com')).toBeInTheDocument();
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });

  it('calls logout when logout button is clicked', () => {
    (useAuthModule.useAuth as Mock).mockReturnValue({
      user: { email: 'test@example.com', user_id: 'user-123' },
      isLoading: false,
      error: null,
      isAuthenticated: true,
      logout: mockLogout,
    });

    render(<Header />);
    fireEvent.click(screen.getByText('Logout'));
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it('shows not authenticated message when not authenticated', () => {
    (useAuthModule.useAuth as Mock).mockReturnValue({
      user: null,
      isLoading: false,
      error: null,
      isAuthenticated: false,
      logout: mockLogout,
    });

    render(<Header />);
    expect(screen.getByText('Not authenticated')).toBeInTheDocument();
  });
});
