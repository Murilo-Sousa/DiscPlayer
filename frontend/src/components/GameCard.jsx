import { Link } from "../router/index.jsx";
import { cx } from "../utils/cx.js";
import { formatRating, formatYear, gamePath, statusLabel } from "../utils/format.js";
import { Cover } from "./Cover.jsx";
import { StatusDisc } from "./Disc.jsx";
import { Icon } from "./Icon.jsx";

/**
 * Capa + título + ano. Com `entry`, mostra o status do jogador no canto da capa
 * (disco) e o coração de favorito; com `rating`, a nota dele.
 */
export function GameCard({ game, entry, rating, caption, ratio = "poster", showYear = true, className }) {
  const year = showYear ? formatYear(game.released) : "";
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
        {year && <span className="game-card-meta">{year}</span>}
        {caption && <span className="game-card-caption">{caption}</span>}
      </Link>
    </article>
  );
}
