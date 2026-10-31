import { Link } from "../router/index.jsx";
import { formatAverage, gamePath, plural } from "../utils/format.js";
import { Cover } from "./Cover.jsx";

/** A lista numerada de "Mais bem avaliados": posição, capa, nome, número de notas e a média. */
export function RankingList({ items }) {
  return (
    <ol className="ranking">
      {items.map((item, index) => (
        <li key={item.game.rawg_id} className="ranking-item">
          <span className="ranking-position" aria-hidden="true">
            {index + 1}
          </span>
          <Link to={gamePath(item.game)} className="ranking-cover" tabIndex={-1} aria-hidden="true">
            <Cover game={item.game} ratio="poster" />
          </Link>
          <span className="ranking-text">
            <Link to={gamePath(item.game)} className="ranking-name">
              {item.game.name}
            </Link>
            <span className="ranking-meta">{plural(item.count, "nota", "notas")}</span>
          </span>
          <span className="ranking-score">
            <span className="sr-only">Média </span>
            {formatAverage(item.average)}
          </span>
        </li>
      ))}
    </ol>
  );
}
