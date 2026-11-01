import { useEffect, useState } from "react";
import { StatusDisc } from "../../components/Disc.jsx";
import { Link, useLocation } from "../../router/index.jsx";
import { STATUS_LABELS } from "../../utils/format.js";

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Barra fixa do celular com o status do jogo no diário. Aparece quando o painel do diário sai da tela e leva até ele
 * (o painel é quem muda o status, com as regras todas). Em telas largas o painel já fica à vista: a barra não aparece.
 */
export function StatusDock({ anchorRef, ready, signedIn, entry }) {
  const [panelOnScreen, setPanelOnScreen] = useState(true);
  const [footerOnScreen, setFooterOnScreen] = useState(false);
  const { pathname, search } = useLocation();

  useEffect(() => {
    const node = anchorRef.current;
    if (!node || typeof IntersectionObserver === "undefined") return undefined;
    const observer = new IntersectionObserver(([item]) => setPanelOnScreen(item.isIntersecting), { threshold: 0.1 });
    observer.observe(node);
    return () => observer.disconnect();
  }, [anchorRef, ready, signedIn]); // o painel só existe depois que a sessão é conhecida

  // No fim da página o rodapé aparece, e a barra sairia na frente dos links dele.
  useEffect(() => {
    const footer = document.querySelector(".site-footer");
    if (!footer || typeof IntersectionObserver === "undefined") return undefined;
    const observer = new IntersectionObserver(([item]) => setFooterOnScreen(item.isIntersecting));
    observer.observe(footer);
    return () => observer.disconnect();
  }, []);

  if (!ready || panelOnScreen || footerOnScreen) return null;

  const goToPanel = () => {
    const node = anchorRef.current;
    if (!node) return;
    node.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    node.querySelector(".status-option")?.focus({ preventScroll: true });
  };

  return (
    <div className="status-dock" role="region" aria-label="Seu registro deste jogo">
      {signedIn ? (
        <>
          <span className="status-dock-state">
            {entry ? (
              <>
                <StatusDisc status={entry.status} size={22} />
                <span>{STATUS_LABELS[entry.status]}</span>
              </>
            ) : (
              <span>Fora do seu diário</span>
            )}
          </span>
          <button type="button" className="btn btn-primary" onClick={goToPanel}>
            {entry ? "Mudar status" : "Registrar"}
          </button>
        </>
      ) : (
        <>
          <span className="status-dock-state">
            <span>Quer registrar este jogo?</span>
          </span>
          <Link to={`/entrar?proximo=${encodeURIComponent(pathname + search)}`} className="btn btn-primary">
            Entrar
          </Link>
        </>
      )}
    </div>
  );
}
