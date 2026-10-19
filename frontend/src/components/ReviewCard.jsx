import { Link } from "../router/index.jsx";
import { cx } from "../utils/cx.js";
import { formatDate, formatRating, gamePath, paragraphs, userPath } from "../utils/format.js";
import { Avatar } from "./Avatar.jsx";
import { Cover } from "./Cover.jsx";
import { RatingDiscs } from "./Disc.jsx";
import { Icon } from "./Icon.jsx";

/**
 * Uma review. O texto é renderizado como texto (React escapa tudo), nunca como HTML.
 * `onLike(review)` é opcional; sem ele, as curtidas aparecem só como contagem.
 */
export function ReviewCard({ review, showGame = false, showAuthor = true, canLike = false, onLike, pending = false, className }) {
  const body = paragraphs(review.body);
  const edited = review.updated_at && review.updated_at !== review.created_at;
  return (
    <article className={cx("review", className)}>
      {showGame && review.game && (
        <Link to={gamePath(review.game)} className="review-game" tabIndex={-1} aria-hidden="true">
          <Cover game={review.game} ratio="poster" />
        </Link>
      )}
      <div className="review-main">
        <header className="review-header">
          {showAuthor && review.user && (
            <Link to={userPath(review.user.username)} className="review-author">
              <Avatar user={review.user} size={28} />
              <span>{review.user.display_name}</span>
            </Link>
          )}
          {showGame && review.game && (
            <>
              {showAuthor && review.user && <span className="review-about">avaliou</span>}
              <Link to={gamePath(review.game)} className="review-game-name">
                {review.game.name}
              </Link>
            </>
          )}
          <span className="review-rating">
            <RatingDiscs value={review.rating} size={13} />
            <span className="review-rating-number">{formatRating(review.rating)}</span>
          </span>
        </header>
        {body.length > 0 && (
          <div className="review-body prose">
            {body.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        )}
        <footer className="review-footer">
          <time dateTime={review.created_at}>{formatDate(review.created_at)}</time>
          {edited && <span className="review-edited">editada em {formatDate(review.updated_at)}</span>}
          {onLike ? (
            <button
              type="button"
              className="like-btn"
              aria-pressed={review.liked}
              disabled={pending}
              onClick={() => onLike(review)}
              title={canLike ? undefined : "Entre na sua conta para curtir"}
            >
              <Icon name="heart" size={16} filled={review.liked} />
              <span>{review.liked ? "Curtida" : "Curtir"}</span>
              <span className="like-count" aria-label={`${review.like_count} curtidas`}>
                {review.like_count}
              </span>
            </button>
          ) : (
            review.like_count > 0 && (
              <span className="like-static">
                <Icon name="heart" size={14} filled />
                {review.like_count}
              </span>
            )
          )}
        </footer>
      </div>
    </article>
  );
}
