import { Link } from "../router/index.jsx";
import { REPLAY_VERB, STATUS_VERBS, formatRating, gamePath, listPath, timeAgo, userPath } from "../utils/format.js";
import { Avatar } from "./Avatar.jsx";
import { Cover } from "./Cover.jsx";
import { RatingDiscs, StatusDisc } from "./Disc.jsx";
import { Icon } from "./Icon.jsx";

/** Uma linha do histórico/feed: quem fez o quê, em qual jogo (ou lista) e quando. */
export function ActivityItem({ activity, showUser = true }) {
  const { type, user, game, review, list } = activity;
  const who = showUser ? (
    <Link to={userPath(user.username)} className="activity-user">
      {user.display_name}
    </Link>
  ) : null;

  return (
    <li className="activity" data-type={type}>
      {showUser ? <Avatar user={user} size={34} /> : <span className="activity-mark" aria-hidden="true">{type === "logged" ? <StatusDisc status={activity.status} size={20} /> : <Icon name={type === "list_created" ? "list" : "edit"} size={18} />}</span>}
      <div className="activity-main">
        <p className="activity-line">
          {who}
          {who ? " " : ""}
          {type === "logged" && (
            <>
              {who ? verbFor(activity) : capitalize(verbFor(activity))}{" "}
              <Link to={gamePath(game)} className="activity-target">
                {game.name}
              </Link>
            </>
          )}
          {type === "reviewed" && (
            <>
              {who ? "avaliou" : "Avaliou"}{" "}
              <Link to={gamePath(game)} className="activity-target">
                {game.name}
              </Link>
            </>
          )}
          {type === "list_created" && (
            <>
              {who ? "criou a lista" : "Criou a lista"}{" "}
              <Link to={listPath(list.id)} className="activity-target">
                {list.title}
              </Link>
            </>
          )}
        </p>
        {type === "reviewed" && (
          <p className="activity-review">
            <RatingDiscs value={review.rating} size={13} />
            <span className="activity-rating">{formatRating(review.rating)}</span>
            {review.has_spoilers ? (
              <span className="activity-spoiler">Contém spoilers. Abra a página do jogo para ler.</span>
            ) : (
              review.excerpt && <span className="activity-excerpt">{review.excerpt}</span>
            )}
          </p>
        )}
        <time className="activity-time" dateTime={activity.created_at}>
          {timeAgo(activity.created_at)}
        </time>
      </div>
      {game && (
        <Link to={gamePath(game)} className="activity-cover" tabIndex={-1} aria-hidden="true">
          <Cover game={game} ratio="poster" />
        </Link>
      )}
    </li>
  );
}

const verbFor = (activity) => (activity.replay ? REPLAY_VERB : STATUS_VERBS[activity.status]);
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);
