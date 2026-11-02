import { Avatar } from "../../components/Avatar.jsx";
import { DemoBadge } from "../../components/DemoBadge.jsx";
import { RatingDiscs, StatusDisc } from "../../components/Disc.jsx";
import { Icon } from "../../components/Icon.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { Link } from "../../router/index.jsx";
import { gamesApi } from "../../services/api.js";
import { formatAverage, formatRating, plural, statusLabel, userPath } from "../../utils/format.js";

/** Uma pessoa seguida: quem é, em que pé está o jogo para ela (status e favorito) e a nota, se deu. */
export function FollowingPlayer({ item }) {
  const { user, status, is_favorite: favorite, rating } = item;
  return (
    <li className="following-item">
      <Avatar user={user} size={32} />
      <div className="following-text">
        <Link to={userPath(user.username)} className="following-name">
          {user.display_name}
          <DemoBadge user={user} />
        </Link>
        {status && (
          <span className="following-status">
            <StatusDisc status={status} size={14} />
            {statusLabel(status)}
            {favorite && (
              <>
                <Icon name="heart" size={13} filled className="following-heart" />
                <span className="sr-only">, favorito</span>
              </>
            )}
          </span>
        )}
      </div>
      {rating !== null && rating !== undefined && (
        <span className="following-rating">
          <RatingDiscs value={rating} size={11} />
          <strong>{formatRating(rating)}</strong>
        </span>
      )}
    </li>
  );
}

/** O conteúdo do bloco, separado do carregamento para poder ser testado com dados prontos. */
export function FollowingPlayersView({ data }) {
  const { items, total, rated, average, want_to_play: wantToPlay } = data;
  if (total === 0 || items.length === 0) return null;
  const hidden = total - items.length;
  return (
    <section className="following-card" aria-labelledby="following-title">
      <h2 id="following-title" className="score-title">
        Quem você segue jogou
      </h2>
      {rated >= 2 && (
        <p className="following-summary">
          Média entre quem você segue: <strong>{formatAverage(average)}</strong> ({plural(rated, "nota", "notas")})
        </p>
      )}
      <ul className="following-list">
        {items.map((item) => (
          <FollowingPlayer key={item.user.username} item={item} />
        ))}
      </ul>
      {(hidden > 0 || wantToPlay > 0) && (
        <p className="following-more">
          {[
            hidden > 0 && `e mais ${plural(hidden, "pessoa", "pessoas")}`,
            wantToPlay > 0 && `${plural(wantToPlay, "pessoa quer", "pessoas querem")} jogar`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}
    </section>
  );
}

/**
 * "Quem você segue jogou": as pessoas que a pessoa logada segue e que já começaram (ou avaliaram) este jogo. É um
 * extra: sem ninguém para mostrar, ou se a consulta falhar, o bloco simplesmente não aparece.
 */
export function FollowingPlayers({ rawgId }) {
  const { user } = useAuth();
  const state = useAsync(
    (signal) => (user ? gamesApi.following(rawgId, { signal }) : Promise.resolve(null)),
    [rawgId, user?.username],
  );
  if (!user || !state.data) return null;
  return <FollowingPlayersView data={state.data} />;
}
