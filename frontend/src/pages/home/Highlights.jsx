import { Avatar } from "../../components/Avatar.jsx";
import { Cover, CoverStack } from "../../components/Cover.jsx";
import { DemoBadge } from "../../components/DemoBadge.jsx";
import { RatingDiscs, StatusDisc } from "../../components/Disc.jsx";
import { Section } from "../../components/Layout.jsx";
import { EmptyState, ErrorState, Skeleton } from "../../components/States.jsx";
import { Link } from "../../router/index.jsx";
import { formatRating, gamePath, listPath, plural, timeAgo, userPath } from "../../utils/format.js";

const VERBS = { finished: "zerou", reviewed: "avaliou", abandonado: "abandonou", pausado: "pausou" };

function Who({ user }) {
  return (
    <>
      <Avatar user={user} size={20} />
      <Link to={userPath(user.username)} className="news-user">
        {user.display_name}
      </Link>
      <DemoBadge user={user} />
    </>
  );
}

function GameLink({ game }) {
  return (
    <Link to={gamePath(game)} className="news-target">
      {game.name}
    </Link>
  );
}

function Time({ at }) {
  return (
    <time className="news-time" dateTime={at}>
      {timeAgo(at)}
    </time>
  );
}

/** Zerou e/ou avaliou: a capa grande, a nota e um trecho da review (nunca de uma review com spoilers). */
function ReviewCard({ card }) {
  const { user, game, kind, rating, excerpt, has_spoilers: spoilers } = card;
  return (
    <>
      <Link to={gamePath(game)} className="news-cover" tabIndex={-1} aria-hidden="true">
        <Cover game={game} ratio="poster" />
      </Link>
      <div className="news-body">
        <p className="news-line">
          <Who user={user} /> {VERBS[kind]} <GameLink game={game} />
        </p>
        {rating !== null && rating !== undefined && (
          <p className="news-review">
            <RatingDiscs value={rating} size={13} />
            <strong className="news-rating">{formatRating(rating)}</strong>
          </p>
        )}
        {spoilers ? (
          <p className="news-excerpt news-spoiler">Contém spoilers. Abra a página do jogo para ler.</p>
        ) : (
          excerpt && <p className="news-excerpt">{excerpt}</p>
        )}
        <Time at={card.created_at} />
      </div>
    </>
  );
}

/** Abandonou ou pausou: uma linha, sem capa. */
function StatusCard({ card }) {
  const { user, game, status } = card;
  return (
    <>
      <span className="news-mark" aria-hidden="true">
        <StatusDisc status={status} size={22} />
      </span>
      <div className="news-body">
        <p className="news-line">
          <Who user={user} /> {VERBS[status]} <GameLink game={game} />
        </p>
        <Time at={card.created_at} />
      </div>
    </>
  );
}

/** Vários jogos guardados na fila de uma vez: uma linha e as capas, em vez de uma linha por jogo. */
function QueuedCard({ card }) {
  const { user, games, count } = card;
  const rest = count - games.length;
  return (
    <>
      <span className="news-mark" aria-hidden="true">
        <StatusDisc status="quero_jogar" size={22} />
      </span>
      <div className="news-body">
        <p className="news-line">
          <Who user={user} /> guardou{" "}
          {count === 1 ? (
            <GameLink game={games[0]} />
          ) : (
            <>
              {count} jogos <span className="news-plain">na fila</span>
            </>
          )}
        </p>
        <ul className="news-minis">
          {games.map((game) => (
            <li key={game.rawg_id}>
              <Link to={gamePath(game)} className="news-mini" title={game.name}>
                <Cover game={game} ratio="poster" />
                <span className="sr-only">{game.name}</span>
              </Link>
            </li>
          ))}
          {rest > 0 && <li className="news-more">+{rest}</li>}
        </ul>
        <Time at={card.created_at} />
      </div>
    </>
  );
}

function ListCard({ card }) {
  const { user, list } = card;
  return (
    <>
      <Link to={listPath(list.id)} className="news-stack" tabIndex={-1} aria-hidden="true">
        <CoverStack covers={list.covers} />
      </Link>
      <div className="news-body">
        <p className="news-line">
          <Who user={user} /> criou a lista{" "}
          <Link to={listPath(list.id)} className="news-target">
            {list.title}
          </Link>
        </p>
        <p className="news-excerpt">{plural(list.game_count, "jogo", "jogos")}</p>
        <Time at={card.created_at} />
      </div>
    </>
  );
}

const RENDER = {
  finished: ReviewCard,
  reviewed: ReviewCard,
  status: StatusCard,
  queued: QueuedCard,
  list: ListCard,
};

export function HighlightCard({ card }) {
  const Body = RENDER[card.kind];
  if (!Body) return null;
  return (
    <li className="news-item" data-kind={card.kind}>
      <Body card={card} />
    </li>
  );
}

/**
 * "Novidades": a atividade recente já agrupada pelo servidor. `data` é a resposta de /api/highlights do escopo atual
 * (ou nulo enquanto carrega).
 */
export function Highlights({ data, scope, error, onRetry }) {
  const ready = data && data.scope === scope;
  return (
    <Section title="Novidades" className="home-news">
      {error && !ready ? (
        <ErrorState error={error} onRetry={onRetry} compact title="Não foi possível carregar as novidades" />
      ) : !ready ? (
        <div className="skeleton-rows" aria-hidden="true">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="skeleton-row" />
          ))}
        </div>
      ) : data.items.length === 0 ? (
        <EmptyState compact title="Nada de novo por aqui">
          {scope === "following"
            ? data.following === 0
              ? "Siga outras pessoas para ver aqui o que elas zeram, avaliam e listam."
              : "Quando alguém que você segue zerar, avaliar um jogo ou criar uma lista, aparece aqui."
            : "Quando alguém zerar, avaliar um jogo ou criar uma lista, aparece aqui."}
        </EmptyState>
      ) : (
        <ul className="news-list">
          {data.items.map((card, index) => (
            <HighlightCard key={`${card.kind}-${card.created_at}-${card.user.username}-${index}`} card={card} />
          ))}
        </ul>
      )}
    </Section>
  );
}
