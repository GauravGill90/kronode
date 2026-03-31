interface LogoProps {
  size?: number;
  className?: string;
}

export default function KronodeLogo({ size = 28, className = "" }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <rect width="64" height="64" rx="14" fill="#d4a853" />
      <path
        d="M32 16 C24 16 18 22 18 30 C18 38 24 44 32 48 C40 44 46 38 46 30 C46 22 40 16 32 16Z"
        stroke="#1c1917"
        strokeWidth="2.5"
        fill="none"
      />
      <line x1="32" y1="22" x2="32" y2="42" stroke="#1c1917" strokeWidth="2" />
      <line x1="24" y1="28" x2="40" y2="28" stroke="#1c1917" strokeWidth="2" />
      <line x1="24" y1="36" x2="40" y2="36" stroke="#1c1917" strokeWidth="2" />
      <circle cx="32" cy="28" r="2.5" fill="#1c1917" />
      <circle cx="32" cy="36" r="2.5" fill="#1c1917" />
      <circle cx="24" cy="28" r="2" fill="#1c1917" />
      <circle cx="40" cy="28" r="2" fill="#1c1917" />
      <circle cx="24" cy="36" r="2" fill="#1c1917" />
      <circle cx="40" cy="36" r="2" fill="#1c1917" />
    </svg>
  );
}
