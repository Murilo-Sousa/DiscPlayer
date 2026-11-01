import { useEffect, useId, useRef, useState } from "react";
import { cx } from "../utils/cx.js";
import { Icon } from "./Icon.jsx";
import { GameCard } from "./GameCard.jsx";
import { Skeleton } from "./States.jsx";

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Um jogo com o que o diário de quem está logado sabe dele: status, favorito e o atalho "guardar na fila".
 * `diary` vem de `useDiaryEntries`; sem login, o card é o comum (com a média da comunidade, se houver).
 */
export function LibraryGameCard({ game, diary, community, showGenre = true }) {
  const entry = diary.entries[game.rawg_id];
  return (
    <GameCard
      game={game}
      entry={entry}
      community={community === undefined ? game.community : community}
      showGenre={showGenre}
      onQuickAdd={diary.enabled && !entry ? () => diary.add(game) : undefined}
      quickAddPending={Boolean(diary.pending[game.rawg_id])}
    />
  );
}

/**
 * Prateleira: uma fileira de jogos que rola de lado (e tem botões para quem usa o mouse). Cada filho é um jogo,
 * dentro de um `<ShelfItem>`.
 */
export function GameShelf({ title, action, children, className }) {
  const id = useId();
  const track = useRef(null);
  const [overflows, setOverflows] = useState(false);
  // Só há o que rolar quando os jogos não cabem na largura: sem isso, os botões não têm serventia.
  useEffect(() => {
    const node = track.current;
    if (node) setOverflows(node.scrollWidth > node.clientWidth + 1);
  });
  useEffect(() => {
    const node = track.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(() => setOverflows(node.scrollWidth > node.clientWidth + 1));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const scroll = (direction) => {
    const node = track.current;
    if (!node) return;
    node.scrollBy({ left: direction * node.clientWidth * 0.85, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  };
  return (
    <section className={cx("shelf", className)} aria-labelledby={id}>
      <div className="section-head">
        <h2 id={id} className="section-title">
          {title}
        </h2>
        <div className="shelf-tools">
          {action}
          {overflows && (
            <span className="shelf-buttons">
              <button type="button" className="btn btn-icon" onClick={() => scroll(-1)} aria-label={`Ver os jogos anteriores de “${title}”`}>
                <Icon name="left" size={18} />
              </button>
              <button type="button" className="btn btn-icon" onClick={() => scroll(1)} aria-label={`Ver mais jogos de “${title}”`}>
                <Icon name="right" size={18} />
              </button>
            </span>
          )}
        </div>
      </div>
      <ul className="shelf-track" ref={track}>
        {children}
      </ul>
    </section>
  );
}

export function ShelfItem({ children }) {
  return <li className="shelf-item">{children}</li>;
}

/** O lugar da prateleira enquanto ela carrega (a página não pula quando os jogos chegam). */
export function ShelfSkeleton({ title, count = 6 }) {
  return (
    <section className="shelf" aria-hidden="true">
      <div className="section-head">
        <h2 className="section-title">{title}</h2>
      </div>
      <ul className="shelf-track">
        {Array.from({ length: count }, (_, index) => (
          <li key={index} className="shelf-item">
            <Skeleton className="skeleton-cover" />
            <Skeleton className="skeleton-line" />
          </li>
        ))}
      </ul>
    </section>
  );
}
