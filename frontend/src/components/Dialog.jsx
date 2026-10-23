import { useEffect, useId, useRef } from "react";
import { Icon } from "./Icon.jsx";

/**
 * Janela modal sobre o elemento <dialog> nativo: foco preso, Esc fecha e o foco volta para quem abriu.
 * Quem decide se a janela fecha é sempre o React (`open`): o Esc só pede para fechar, via `onClose`.
 * Assim, quem ignora o pedido (por exemplo, durante um envio em andamento) não fica com o <dialog>
 * fechado por baixo enquanto o estado diz que ele está aberto.
 */
export function Dialog({ open, onClose, title, children, wide = false }) {
  const ref = useRef(null);
  const titleId = useId();
  const openRef = useRef(open);

  useEffect(() => {
    openRef.current = open;
  });

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
      onCancel={(event) => {
        event.preventDefault(); // o navegador não fecha sozinho; o React fecha se `open` virar false
        onClose();
      }}
      onClose={() => {
        // Fechamento que escapou do onCancel (o Chrome fecha no segundo Esc seguido): pede o fechamento e,
        // se o pai recusou, reabre.
        if (!openRef.current) return;
        onClose();
        setTimeout(() => {
          const dialog = ref.current;
          if (dialog && openRef.current && !dialog.open) dialog.showModal();
        }, 0);
      }}
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
