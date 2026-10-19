import { useId } from "react";
import { formatRating } from "../utils/format.js";
import { RatingDiscs } from "./Disc.jsx";

/**
 * Nota de 0 a 10 em passos de 0,5: um controle deslizante nativo (funciona com
 * teclado e leitor de tela) com os cinco discos como pré-visualização.
 * `value` é null enquanto a pessoa ainda não escolheu uma nota.
 */
export function RatingInput({ value, onChange, disabled = false }) {
  const id = useId();
  const commit = (event) => onChange(Number(event.currentTarget.value));
  return (
    <div className="rating-input" data-empty={value === null || undefined}>
      <div className="rating-input-readout">
        <RatingDiscs value={value} size={24} />
        <output htmlFor={id} className="rating-input-value">
          {value === null ? "Sem nota" : formatRating(value)}
        </output>
        {value !== null && (
          <button type="button" className="link-btn" onClick={() => onChange(null)} disabled={disabled}>
            Limpar nota
          </button>
        )}
      </div>
      <input
        id={id}
        className="rating-input-range"
        type="range"
        min="0"
        max="10"
        step="0.5"
        value={value ?? 5}
        disabled={disabled}
        aria-label="Nota de 0 a 10"
        aria-valuetext={value === null ? "Sem nota" : `${formatRating(value)} de 10`}
        onChange={commit}
        // Clicar no ponto onde o controle já está (5) não dispara "change": registra aqui.
        onPointerUp={(event) => value === null && commit(event)}
      />
      <div className="rating-input-scale" aria-hidden="true">
        <span>0</span>
        <span>5</span>
        <span>10</span>
      </div>
    </div>
  );
}
