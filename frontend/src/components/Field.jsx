import { useId } from "react";
import { cx } from "../utils/cx.js";

/** Campo de formulário com rótulo, dica e mensagem de erro ligados por aria-describedby. */
export function Field({ label, error, hint, as = "input", maxLength, value, className, children, ...props }) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(" ") || undefined;
  const Control = as;
  const control =
    as === "select" ? (
      <select id={id} aria-invalid={!!error} aria-describedby={describedBy} value={value} {...props}>
        {children}
      </select>
    ) : (
      <Control
        id={id}
        aria-invalid={!!error}
        aria-describedby={describedBy}
        maxLength={maxLength}
        value={value}
        {...props}
      />
    );
  return (
    <div className={cx("field", className)} data-invalid={error ? "true" : undefined}>
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      {control}
      {as === "textarea" && maxLength && typeof value === "string" && (
        <p className="field-counter" aria-hidden="true">
          {value.length}/{maxLength}
        </p>
      )}
      {hint && (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="field-error">
          {error}
        </p>
      )}
    </div>
  );
}
