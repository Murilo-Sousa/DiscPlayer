import { Link } from "../router/index.jsx";
import { cx } from "../utils/cx.js";
import { formatAverage, formatRating, formatYear, gamePath, plural, statusLabel } from "../utils/format.js";
import { Cover } from "./Cover.jsx";
import { Disc, StatusDisc } from "./Disc.jsx";
import { Icon } from "./Icon.jsx";

/**
 * Capa + título + ano. Com `entry`, mostra o status do jogador no canto da capa
 * (disco) e o coração de favorito; com `rating`, a nota dele.
 *
 * Para o catálogo e as prateleiras: `showGenre` põe o primeiro gênero ao lado do ano; `community` ({average, count})
 * mostra a média do DiscPlayer com o número de notas; `onQuickAdd` oferece o botão "+" que guarda o jogo na fila
 * (só quando o jogo ainda não está no diário).
 */
export function GameCard({
  game,
  entry,
  rating,
  caption,
  ratio = "poster",
  showYear = true,
  showGenre = false,
  community,
  onQuickAdd,
  quickAddPending = false,
  className,
}) {
  const year = showYear ? formatYear(game.released) : "";
  const genre = showGenre ? game.genres?.[0] : "";
  const meta = [year, genre].filter(Boolean).join(" · ");
  const average = community && community.count > 0 ? formatAverage(community.average) : null;
  return (
    <article className={cx("game-card", className)} data-ratio={ratio}>
      <Link to={gamePath(game)} className="game-card-link">
        <span className="game-card-cover">
          <Cover game={game} ratio={ratio} />
          {entry && (
            <span className="game-card-flags">
              <StatusDisc status={entry.status} size={18} />
              <span className="sr-only">{statusLabel(entry.status)}</span>
              {entry.is_favorite && (
                <>
                  <Icon name="heart" size={15} filled className="game-card-heart" />
                  <span className="sr-only">Favorito</span>
                </>
              )}
            </span>
          )}
          {rating !== null && rating !== undefined && (
            <span className="game-card-rating">
              <span className="sr-only">Sua nota: </span>
              {formatRating(rating)}
            </span>
          )}
        </span>
        <span className="game-card-title">{game.name}</span>
        {meta && <span className="game-card-meta">{meta}</span>}
        {average && (
          <span className="game-card-community">
            <Disc className="game-card-community-disc" size={13} quarters={4} />
            <strong aria-hidden="true">{average}</strong>
            <span className="game-card-count" aria-hidden="true">
              ({community.count})
            </span>
            <span className="sr-only">
              Média {average} em {plural(community.count, "nota", "notas")} no DiscPlayer
            </span>
          </span>
        )}
        {caption && <span className="game-card-caption">{caption}</span>}
      </Link>
      {onQuickAdd && !entry && (
        <button
          type="button"
          className="game-card-add"
          onClick={onQuickAdd}
          disabled={quickAddPending}
          aria-busy={quickAddPending || undefined}
          aria-label={`Guardar ${game.name} em Quero jogar`}
          title="Guardar em Quero jogar"
        >
          <Icon name="plus" size={16} />
        </button>
      )}
    </article>
  );
}
