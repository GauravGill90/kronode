import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 7,
          background: "#d4a853",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M32 8 C20 8 12 18 12 30 C12 42 20 52 32 58 C44 52 52 42 52 30 C52 18 44 8 32 8Z"
            stroke="#1c1917"
            strokeWidth="4"
            fill="none"
          />
          <line x1="32" y1="18" x2="32" y2="48" stroke="#1c1917" strokeWidth="3.5" />
          <line x1="20" y1="27" x2="44" y2="27" stroke="#1c1917" strokeWidth="3.5" />
          <line x1="20" y1="39" x2="44" y2="39" stroke="#1c1917" strokeWidth="3.5" />
          <circle cx="32" cy="27" r="4" fill="#1c1917" />
          <circle cx="32" cy="39" r="4" fill="#1c1917" />
          <circle cx="20" cy="27" r="3" fill="#1c1917" />
          <circle cx="44" cy="27" r="3" fill="#1c1917" />
          <circle cx="20" cy="39" r="3" fill="#1c1917" />
          <circle cx="44" cy="39" r="3" fill="#1c1917" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
