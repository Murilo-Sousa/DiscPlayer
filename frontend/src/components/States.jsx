import { cx } from "../utils/cx.js";
import { Disc } from "./Disc.jsx";

export function Skeleton({ className, style }) {
  return <span className={cx("skeleton", className)} style={style} aria-hidden="true" />;
}

/** Disco girando (quando o usuário aceita animações). */
export function Loader({ label = "Carregando" }) {
  return (
    <span className="loader" role="status">
      <Disc quarters={1} size={22} className="loader-disc" />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function ErrorState({ error, title = "Não foi possível carregar", onRetry, compact = false }) {
  return (
    <div className={cx("state", "state-error", compact && "state-compact")} role="alert">
      <h3 className="state-title">{title}</h3>
      <p className="state-text">{error?.message ?? "Tente novamente em instantes."}</p>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Tentar de novo
        </button>
      )}
    </div>
  );
}

/** `level` é o nível do título (h3 por padrão); use 2 quando o estado vem logo depois do h1 da página. */
export function EmptyState({ title, children, action, compact = false, level = 3 }) {
  const Heading = `h${level}`;
  return (
    <div className={cx("state", compact && "state-compact")}>
      <Heading className="state-title">{title}</Heading>
      {children && <div className="state-text">{children}</div>}
      {action && <div className="state-action">{action}</div>}
    </div>
  );
}

/**
 * Resolve os quatro estados de uma busca de dados: carregando, erro, vazio e pronto.
 * `children` recebe os dados. Durante um recarregamento os dados antigos continuam na tela.
 */
export function Async({ state, skeleton, empty, isEmpty, errorTitle, children }) {
  if (state.error && !state.data) {
    return <ErrorState error={state.error} title={errorTitle} onRetry={state.reload} />;
  }
  if (!state.data) return skeleton ?? <Loader />;
  if (isEmpty?.(state.data)) return empty ?? null;
  return <div aria-busy={state.loading || undefined}>{children(state.data)}</div>;
}
