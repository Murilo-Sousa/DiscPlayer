import { StatusDisc } from "./Disc.jsx";
import { STATUS_LABELS, STATUS_PROGRESS } from "../utils/format.js";

/**
 * Os cinco status do diário, do jogo que ainda não começou ao que foi largado.
 * `blocked` diz quais status não podem ser escolhidos agora ({ status: motivo }); quem usa mostra os motivos por escrito
 * e aponta para eles com `describedBy`.
 */
export function StatusPicker({ value, onChange, disabled = false, label = "Status do jogo", blocked = {}, describedBy }) {
  return (
    <div className="status-picker" role="group" aria-label={label} aria-describedby={describedBy}>
      {STATUS_PROGRESS.map((status) => (
        <button
          key={status}
          type="button"
          className="status-option"
          data-status={status}
          aria-pressed={value === status}
          disabled={disabled || Boolean(blocked[status])}
          title={blocked[status] || undefined}
          onClick={() => onChange(status)}
        >
          <StatusDisc status={status} size={20} />
          <span>{STATUS_LABELS[status]}</span>
        </button>
      ))}
    </div>
  );
}

export function StatusBadge({ status, className }) {
  return (
    <span className={`status-badge ${className ?? ""}`.trim()} data-status={status}>
      <StatusDisc status={status} size={16} />
      {STATUS_LABELS[status]}
    </span>
  );
}
