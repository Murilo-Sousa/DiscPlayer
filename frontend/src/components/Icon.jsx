import { cx } from "../utils/cx.js";

// Ícones de traço (24x24). Só os usados pela interface.
const PATHS = {
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m16 16 5 5" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  heart: <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />,
  left: <path d="m14.5 6-6 6 6 6" />,
  right: <path d="m9.5 6 6 6-6 6" />,
  up: <path d="M12 19V5M6 11l6-6 6 6" />,
  down: <path d="M12 5v14M6 13l6 6 6-6" />,
  edit: <path d="m4 20 1-4L16.5 4.5a2 2 0 0 1 3 3L8 19l-4 1z" />,
  trash: <path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12" />,
  lock: <><rect x="6" y="11" width="12" height="9" rx="1" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  logout: <path d="M10 5H6v14h4M14 8l4 4-4 4M18 12H9" />,
  home: <path d="m4 11 8-7 8 7v8h-5v-5H9v5H4z" />,
  list: <path d="M8 7h12M8 12h12M8 17h12M4 7h.01M4 12h.01M4 17h.01" />,
  user: <><circle cx="12" cy="8" r="3.5" /><path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6" /></>,
  book: <path d="M6 4h11a1 1 0 0 1 1 1v15H7a1 1 0 0 1-1-1zM9 8h6M9 12h6" />,
  external: <path d="M14 5h5v5M19 5l-8 8M18 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4" />,
  grip: <path d="M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01" />,
};

export function Icon({ name, size = 20, filled = false, className }) {
  return (
    <svg
      className={cx("icon", className)}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}
