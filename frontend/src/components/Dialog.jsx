import { useEffect, useId, useRef } from "react";
import { Icon } from "./Icon.jsx";

/** Janela modal sobre o elemento <dialog> nativo: foco preso, Esc fecha e o foco volta para quem abriu. */
export function Dialog({ open, onClose, title, children, wide = false }) {
  const ref = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="dialog"
      data-wide={wide || undefined}
      aria-labelledby={titleId}
      onClose={() => open && onClose()}
      onClick={(event) => {
        if (event.target === ref.current) onClose(); // clique no fundo escurecido
      }}
    >
      {open && (
        <div className="dialog-body">
          <header className="dialog-header">
            <h2 id={titleId} className="dialog-title">
              {title}
            </h2>
            <button type="button" className="icon-btn" onClick={onClose} aria-label="Fechar">
              <Icon name="x" />
            </button>
          </header>
          {children}
        </div>
      )}
    </dialog>
  );
}
