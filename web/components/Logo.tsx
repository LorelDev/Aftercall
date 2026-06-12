export default function Logo({
  className = "h-8 w-8",
  animated = false,
}: {
  className?: string;
  animated?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={`${className} ${animated ? "logo-draw" : ""}`}
      role="img"
      aria-label="בסדר"
    >
      <path
        d="M7 40h11l6-10 8 18 18-32"
        fill="none"
        stroke="currentColor"
        strokeWidth="6.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
