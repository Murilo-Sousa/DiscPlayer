import { Link } from "../router/index.jsx";
import { listPath, plural, userPath } from "../utils/format.js";
import { CoverStack } from "./Cover.jsx";
import { Icon } from "./Icon.jsx";
import { DemoBadge } from "./DemoBadge.jsx";

/** Lista com a composição das capas dos primeiros jogos. */
export function ListCard({ list, showOwner = true }) {
  return (
    <article className="list-card">
      <Link to={listPath(list.id)} className="list-card-link">
        <CoverStack covers={list.covers} />
        <span className="list-card-title">
          {list.title}
          {!list.is_public && (
            <>
              <Icon name="lock" size={14} className="list-card-lock" />
              <span className="sr-only"> (privada)</span>
            </>
          )}
        </span>
        <span className="list-card-meta">{plural(list.game_count, "jogo", "jogos")}</span>
      </Link>
      {showOwner && (
        <Link to={userPath(list.owner.username)} className="list-card-owner">
          por {list.owner.display_name}
          <DemoBadge user={list.owner} />
        </Link>
      )}
    </article>
  );
}
