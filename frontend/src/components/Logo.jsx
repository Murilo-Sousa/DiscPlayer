import { Link } from "../router/index.jsx";

const MARK_PATH = "M12 8.6V3.4A8.6 8.6 0 0 1 20.6 12h-5.2A3.4 3.4 0 0 0 12 8.6z";

/** Logotipo: um disco com um quarto preenchido (o quarto é a menor nota possível) e o nome em Adventor Bold. */
export function LogoMark({ size = 28 }) {
  return (
    <svg className="logo-mark" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="10.4" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d={MARK_PATH} fill="var(--accent)" />
      <circle cx="12" cy="12" r="3.4" fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.55" />
    </svg>
  );
}

export function Logo({ size = 28 }) {
  return (
    <Link to="/" className="logo" aria-label="DiscPlayer, página inicial">
      <LogoMark size={size} />
      <span className="logo-word">DiscPlayer</span>
    </Link>
  );
}
