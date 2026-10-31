import { useEffect, useRef, useState } from "react";
import { Link } from "../router/index.jsx";
import { cx } from "../utils/cx.js";
import { formatDate, formatRating, gamePath, paragraphs, userPath } from "../utils/format.js";
import { Avatar } from "./Avatar.jsx";
import { Cover } from "./Cover.jsx";
import { RatingDiscs } from "./Disc.jsx";
import { Icon } from "./Icon.jsx";
import { DemoBadge } from "./DemoBadge.jsx";

/**
 * Uma review. O texto é renderizado como texto (React escapa tudo), nunca como HTML.
 * `onLike(review)` é opcional; sem ele, as curtidas aparecem só como contagem.
 * Reviews com `has_spoilers` escondem o texto atrás de um aviso: o texto só entra na página depois do
 * clique (`alwaysShow` dispensa o aviso, para o autor ver o que escreveu).
 */
export function ReviewCard({ review, showGame = false, showAuthor = true, canLike = false, onLike, pending = false, alwaysShow = false, className }) {
  const body = paragraphs(review.body);
  const edited = review.updated_at && review.updated_at !== review.created_at;
  const [revealed, setRevealed] = useState(false);
  const bodyRef = useRef(null);
  const showRef = useRef(null);
  const refocusShow = useRef(false);
  const spoiler = Boolean(review.has_spoilers) && body.length > 0;
  const hidden = spoiler && !revealed && !alwaysShow;
  useEffect(() => {
    if (revealed) bodyRef.current?.focus(); // o botão some ao revelar: o foco vai para o texto
    else if (refocusShow.current) {
      refocusShow.current = false;
      showRef.current?.focus(); // e ao esconder de novo, volta para o botão "Mostrar texto"
    }
  }, [revealed]);
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
              <DemoBadge user={review.user} />
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
          {spoiler && <span className="spoiler-tag">Contém spoilers</span>}
        </header>
        {hidden ? (
          <div className="spoiler-warning">
            <p>Esta review conta partes da história.</p>
            <button type="button" className="btn" aria-expanded="false" ref={showRef} onClick={() => setRevealed(true)}>
              Mostrar texto
            </button>
          </div>
        ) : (
          body.length > 0 && (
            <div className="review-body prose" ref={bodyRef} tabIndex={revealed ? -1 : undefined}>
              {body.map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </div>
          )
        )}
        {spoiler && revealed && !alwaysShow && (
          <button
            type="button"
            className="link-btn spoiler-hide"
            onClick={() => {
              refocusShow.current = true;
              setRevealed(false);
            }}
          >
            Esconder o texto de novo
          </button>
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
