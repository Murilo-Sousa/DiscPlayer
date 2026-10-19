import { useId } from "react";
import { cx } from "../utils/cx.js";
import { ActivityItem } from "./ActivityItem.jsx";
import { Skeleton } from "./States.jsx";

/** Cabeçalho de página: título, texto de apoio e ações. */
export function PageHeader({ title, lead, actions, eyebrow, className }) {
  return (
    <header className={cx("page-header", className)}>
      <div className="page-header-text">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="page-title">{title}</h1>
        {lead && <p className="page-lead">{lead}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  );
}

/** Seção com título (h2) e uma ação opcional à direita (por exemplo, "Ver tudo"). */
export function Section({ title, action, children, className, headingLevel = 2 }) {
  const id = useId();
  const Heading = `h${headingLevel}`;
  return (
    <section className={cx("section", className)} aria-labelledby={id}>
      <div className="section-head">
        <Heading id={id} className="section-title">
          {title}
        </Heading>
        {action}
      </div>
      {children}
    </section>
  );
}

export function GameGrid({ children, className, dense = false }) {
  return (
    <div className={cx("game-grid", className)} data-dense={dense || undefined}>
      {children}
    </div>
  );
}

export function GameGridSkeleton({ count = 12 }) {
  return (
    <GameGrid>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="game-card-skeleton" aria-hidden="true">
          <Skeleton className="skeleton-cover" />
          <Skeleton className="skeleton-line" />
        </div>
      ))}
    </GameGrid>
  );
}

export function ActivityList({ items, showUser = true }) {
  return (
    <ul className="activity-list">
      {items.map((activity) => (
        <ActivityItem key={activity.id} activity={activity} showUser={showUser} />
      ))}
    </ul>
  );
}

export function ListSkeleton({ rows = 4 }) {
  return (
    <div className="skeleton-rows" aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="skeleton-row" />
      ))}
    </div>
  );
}

/** Número em destaque com rótulo (estatísticas do perfil e do jogo). */
export function Stat({ value, label, hint }) {
  return (
    <div className="stat">
      <dt className="stat-label">{label}</dt>
      <dd className="stat-value">{value}</dd>
      {hint && <dd className="stat-hint">{hint}</dd>}
    </div>
  );
}

/**
 * Histograma em barras de CSS, com uma tabela só para leitores de tela.
 * `values` e `labels` têm o mesmo tamanho.
 */
export function Histogram({ values, labels, srLabels = labels, caption, unit = "", emptyText }) {
  const max = Math.max(1, ...values);
  const total = values.reduce((sum, value) => sum + value, 0);
  return (
    <figure className="histogram">
      <figcaption className="sr-only">{caption}</figcaption>
      <div className="histogram-bars" aria-hidden="true">
        {values.map((value, index) => (
          <div className="histogram-col" key={index}>
            <span className="histogram-count">{value > 0 ? value : ""}</span>
            <span className="histogram-bar" style={{ "--h": value / max }} data-empty={value === 0 || undefined} />
            <span className="histogram-label">{labels[index]}</span>
          </div>
        ))}
      </div>
      {total === 0 && emptyText && <p className="histogram-empty">{emptyText}</p>}
      <div className="sr-only">
        <table>
          <caption>{caption}</caption>
          <tbody>
            {values.map((value, index) => (
              <tr key={index}>
                <th scope="row">{srLabels[index]}</th>
                <td>
                  {value}
                  {unit}
                </td>
              </tr>
            ))}
            <tr>
              <th scope="row">Total</th>
              <td>{total}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </figure>
  );
}
