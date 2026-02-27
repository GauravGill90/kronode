interface WelcomeBannerProps {
  userName: string | null;
}

export default function WelcomeBanner({ userName }: WelcomeBannerProps) {
  const greeting = userName ? `Welcome back, ${userName}` : "Welcome back";

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">{greeting} 👋</h1>
      <p className="text-sm text-gray-500 mt-1">Here's what your agent has been up to.</p>
    </div>
  );
}
