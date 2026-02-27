import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { useUser } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import WelcomePage from '../page';

// Mock Clerk
jest.mock('@clerk/nextjs', () => ({
  useUser: jest.fn(),
  SignInButton: ({ children }: { children?: React.ReactNode }) => (
    <button data-testid="sign-in-button">{children || 'Sign In'}</button>
  ),
  SignUpButton: ({ children }: { children?: React.ReactNode }) => (
    <button data-testid="sign-up-button">{children || 'Sign Up'}</button>
  ),
}));

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock color tokens
jest.mock('@/tokens/colors', () => ({
  colors: {
    bg: { base: 'rgb(10, 10, 10)' },
    text: { primary: 'rgb(255, 255, 255)' },
    brand: { primary: 'rgb(100, 200, 255)' },
    glow: { primary: 'rgba(100, 200, 255, 0.5)' },
  },
  gradients: {
    glowTop: 'linear-gradient(to bottom, rgba(100, 200, 255, 0.3), transparent)',
    glowBottomLeft: 'linear-gradient(to top, rgba(150, 100, 255, 0.3), transparent)',
    glowBottomRight: 'linear-gradient(to top, rgba(100, 150, 255, 0.3), transparent)',
    gridOverlay: 'linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px)',
    brandLogo: 'linear-gradient(135deg, rgb(100, 200, 255), rgb(150, 100, 255))',
    brandText: 'linear-gradient(135deg, rgb(100, 200, 255), rgb(150, 100, 255))',
    brandAccent: 'linear-gradient(90deg, rgb(100, 200, 255), rgb(150, 100, 255))',
  },
}));

const mockUseUser = useUser as jest.MockedFunction<typeof useUser>;
const mockUseRouter = useRouter as jest.MockedFunction<typeof useRouter>;

describe('WelcomePage', () => {
  const mockPush = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRouter.mockReturnValue({
      push: mockPush,
      replace: jest.fn(),
      back: jest.fn(),
      forward: jest.fn(),
      refresh: jest.fn(),
      prefetch: jest.fn(),
    } as any);
  });

  describe('Happy path - unauthenticated user', () => {
    it('should render welcome page with all UI elements when user is not signed in', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
        user: null,
      } as any);

      render(<WelcomePage />);

      // Check for main heading
      const heading = screen.getByText('kronode');
      expect(heading).toBeInTheDocument();

      // Check for tagline
      expect(screen.getByText('autonomous AI developer')).toBeInTheDocument();

      // Check for main description
      expect(screen.getByText(/Describe what to build/i)).toBeInTheDocument();

      // Check for authentication buttons
      const signUpButton = screen.getByTestId('sign-up-button');
      const signInButton = screen.getByTestId('sign-in-button');
      expect(signUpButton).toBeInTheDocument();
      expect(signInButton).toBeInTheDocument();

      // Verify no redirect happened
      expect(mockPush).not.toHaveBeenCalled();
    });

    it('should display the logo with correct styling', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
        user: null,
      } as any);

      render(<WelcomePage />);

      // Check for logo text "K"
      const logoText = screen.getByText('K');
      expect(logoText).toBeInTheDocument();
      expect(logoText).toHaveClass('font-bold', 'text-2xl');
    });
  });

  describe('Authenticated user redirect', () => {
    it('should redirect to /onboarding when user is signed in', async () => {
      mockUseUser.mockReturnValue({
        isSignedIn: true,
        isLoaded: true,
        user: { id: 'user123' } as any,
      });

      render(<WelcomePage />);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/onboarding');
      });
    });

    it('should not redirect when loading is not complete', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: true,
        isLoaded: false,
        user: null,
      } as any);

      render(<WelcomePage />);

      // Should not redirect while loading
      expect(mockPush).not.toHaveBeenCalled();
    });
  });

  describe('Edge cases and state transitions', () => {
    it('should not redirect when isLoaded is false even if isSignedIn is true', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: true,
        isLoaded: false,
        user: null,
      } as any);

      render(<WelcomePage />);

      expect(mockPush).not.toHaveBeenCalled();
    });

    it('should handle state transition from loading to authenticated', async () => {
      const { rerender } = render(<WelcomePage />);

      // First render: loading
      mockUseUser.mockReturnValue({
        isSignedIn: false,
        isLoaded: false,
        user: null,
      } as any);
      rerender(<WelcomePage />);

      expect(mockPush).not.toHaveBeenCalled();

      // Second render: loaded and authenticated
      mockUseUser.mockReturnValue({
        isSignedIn: true,
        isLoaded: true,
        user: { id: 'user123' } as any,
      });
      rerender(<WelcomePage />);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/onboarding');
      });
    });

    it('should render all decorative elements with correct styling', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
        user: null,
      } as any);

      const { container } = render(<WelcomePage />);

      // Check for ambient glow elements
      const glowElements = container.querySelectorAll('[class*="rounded-full"]');
      expect(glowElements.length).toBeGreaterThan(0);

      // Check for grid overlay
      const gridOverlay = container.querySelector('[class*="grid"]');
      expect(gridOverlay).toBeInTheDocument();
    });

    it('should have correct z-index for content and decorative elements', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
        user: null,
      } as any);

      const { container } = render(<WelcomePage />);

      // Main content should have z-10
      const mainContent = container.querySelector('[class*="z-10"]');
      expect(mainContent).toBeInTheDocument();

      // Decorative elements should not block interaction (pointer-events-none)
      const decorativeElements = container.querySelectorAll('[class*="pointer-events-none"]');
      expect(decorativeElements.length).toBeGreaterThan(0);
    });
  });

  describe('Null and error cases', () => {
    it('should handle missing user object gracefully', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
        user: null,
      } as any);

      const { container } = render(<WelcomePage />);

      // Page should still render without errors
      expect(container).toBeInTheDocument();
      expect(screen.getByText('kronode')).toBeInTheDocument();
    });

    it('should handle router push errors gracefully', async () => {
      mockPush.mockRejectedValueOnce(new Error('Navigation failed'));

      mockUseUser.mockReturnValue({
        isSignedIn: true,
        isLoaded: true,
        user: { id: 'user123' } as any,
      });

      // Should not throw and component should render
      expect(() => {
        render(<WelcomePage />);
      }).not.toThrow();
    });

    it('should maintain correct layout with minimal content', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
        user: null,
      } as any);

      const { container } = render(<WelcomePage />);

      // Check main layout structure
      const mainDiv = container.querySelector('[class*="min-h-screen"]');
      expect(mainDiv).toHaveClass('flex', 'flex-col', 'items-center', 'justify-center');
    });
  });

  describe('Accessibility', () => {
    it('should have proper heading hierarchy', () => {
      mockUseUser.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
        user: null,
      } as any);

      render(<WelcomePage />);

      // Main heading should exist
      const mainHeading = screen.getByRole('heading', { level: 1 });
      expect(mainHeading).toBeInTheDocument();
    });
  });
});
