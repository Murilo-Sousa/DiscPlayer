// O disco é o motivo visual do DiscPlayer: o logotipo, a nota e o status do jogo
// usam a mesma geometria, em quartos. Um quarto preenchido = 0,5 ponto de nota
// ou um quarto do caminho percorrido no jogo.
import { cx } from "../utils/cx.js";

const OUTER = 8.6;
const INNER = 3.4;
// Quarto superior direito: do furo central até a borda, no sentido horário.
const QUARTER_PATH = `M12 ${12 - INNER}V${12 - OUTER}A${OUTER} ${OUTER} 0 0 1 ${12 + OUTER} 12H${12 + INNER}A${INNER} ${INNER} 0 0 0 12 ${12 - INNER}Z`;

/**
 * @param quarters 0 a 4 quartos preenchidos (sentido horário, a partir das 12h)
 * @param dashed   anel tracejado (jogo que ainda não começou)
 * @param slash    risco diagonal (jogo abandonado)
 */
export function Disc({ quarters = 0, size = 16, dashed = false, slash = false, className, ...rest }) {
  const filled = Math.max(0, Math.min(4, Math.round(quarters)));
  return (
    <svg
      className={cx("disc", className)}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <circle
        cx="12"
        cy="12"
        r="10.4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeDasharray={dashed ? "2.6 2.6" : undefined}
        opacity={filled === 0 ? 0.75 : 1}
      />
      {Array.from({ length: filled }, (_, index) => (
        <path key={index} d={QUARTER_PATH} fill="currentColor" transform={`rotate(${index * 90} 12 12)`} />
      ))}
      <circle cx="12" cy="12" r={INNER} fill="none" stroke="currentColor" strokeWidth="1.1" opacity="0.5" />
      {slash && <path d="M5.6 18.4 18.4 5.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />}
    </svg>
  );
}

export const STATUS_DISC = {
  quero_jogar: { quarters: 0, dashed: true },
  jogando: { quarters: 1 },
  pausado: { quarters: 2 },
  zerado: { quarters: 4 },
  abandonado: { quarters: 0, slash: true },
};

export function StatusDisc({ status, size = 16, className }) {
  const shape = STATUS_DISC[status] ?? { quarters: 0, dashed: true };
  return <Disc size={size} className={cx("status-disc", className)} {...shape} data-status={status} />;
}

/** Nota em cinco discos (cada disco = 2 pontos; cada quarto = 0,5). */
export function RatingDiscs({ value, size = 14, className }) {
  const rating = value === null || value === undefined ? null : Number(value);
  return (
    <span
      className={cx("rating-discs", className)}
      role="img"
      aria-label={rating === null ? "Sem nota" : `Nota ${String(rating).replace(".", ",")} de 10`}
    >
      {Array.from({ length: 5 }, (_, index) => (
        <Disc key={index} size={size} quarters={rating === null ? 0 : (rating - index * 2) / 0.5} />
      ))}
    </span>
  );
}
