import { Avatar } from "../../components/Avatar.jsx";
import { DemoBadge } from "../../components/DemoBadge.jsx";
import { StatusDisc } from "../../components/Disc.jsx";
import { Cover } from "../../components/Cover.jsx";
import { GameShelf, ShelfItem } from "../../components/GameShelf.jsx";
import { EmptyState, ErrorState, Skeleton } from "../../components/States.jsx";
import { Link } from "../../router/index.jsx";
import { gamePath, playingFor, timeAgo, userPath } from "../../utils/format.js";

export const SCOPES = [
  { value: "following", label: "Quem eu sigo" },
  { value: "community", label: "Comunidade" },
];

/** Escolhe de quem é a atividade mostrada no início. Vale para o "jogando agora" e para as novidades. */
export function ScopeSwitch({ scope, onChange }) {
  return (
    <div className="scope-switch" role="group" aria-label="Mostrar a atividade de">
      {SCOPES.map((item) => (
        <button key={item.value} type="button" className="genre-chip" aria-pressed={scope === item.value} onClick={() => onChange(item.value)}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

/** O que a pessoa joga: capa grande, quem é, o jogo e há quanto tempo (ou desde quando foi marcado). */
export function PlayerCard({ item }) {
  const { user, game, started_at: startedAt, since, also } = item;
  const time = playingFor(startedAt) ?? `Marcou ${timeAgo(since)}`;
  return (
    <article className="player-card">
      <Link to={gamePath(game)} className="player-card-cover" tabIndex={-1} aria-hidden="true">
        <Cover game={game} ratio="poster" />
      </Link>
      <div className="player-card-who">
        <Avatar user={user} size={22} />
        <Link to={userPath(user.username)} className="player-card-user">
          {user.display_name}
        </Link>
        <DemoBadge user={user} />
      </div>
      <Link to={gamePath(game)} className="player-card-game">
        {game.name}
      </Link>
      <span className="player-card-meta">
        <StatusDisc status="jogando" size={13} />
        <span>
          {time}
          {also > 0 && ` · +${also} ${also === 1 ? "jogo" : "jogos"}`}
        </span>
      </span>
    </article>
  );
}

function PlayingSkeleton() {
  return Array.from({ length: 5 }, (_, index) => (
    <ShelfItem key={index}>
      <Skeleton className="skeleton-cover" />
      <Skeleton className="skeleton-line" />
    </ShelfItem>
  ));
}

/**
 * "Jogando agora": uma fileira com um cartão por pessoa. `data` é a resposta de /api/playing do escopo atual
 * (ou nulo enquanto carrega). Sem ninguém jogando, o aviso ocupa o lugar da fileira e o seletor continua à mão.
 */
export function PlayingRail({ data, scope, error, onRetry, onScope }) {
  const action = <ScopeSwitch scope={scope} onChange={onScope} />;
  const ready = data && data.scope === scope;
  let placeholder = null;
  if (error && !ready) {
    placeholder = <ErrorState error={error} onRetry={onRetry} compact title="Não foi possível carregar quem está jogando" />;
  } else if (ready && scope === "following" && data.following === 0) {
    placeholder = (
      <EmptyState
        compact
        title="Você ainda não segue ninguém"
        action={
          <>
            <Link to="/buscar" className="btn btn-primary">
              Procurar jogadores
            </Link>
            <button type="button" className="btn" onClick={() => onScope("community")}>
              Ver a comunidade
            </button>
          </>
        }
      >
        Siga outras pessoas para ver aqui o que elas estão jogando e avaliando.
      </EmptyState>
    );
  } else if (ready && data.items.length === 0) {
    placeholder = (
      <EmptyState compact title={scope === "following" ? "Ninguém que você segue está jogando agora" : "Ninguém está jogando agora"}>
        {scope === "following"
          ? "Quando alguém que você segue marcar um jogo como “Jogando”, ele aparece aqui."
          : "Quando alguém marcar um jogo como “Jogando”, ele aparece aqui."}
      </EmptyState>
    );
  }
  return (
    <GameShelf title="Jogando agora" action={action} className="home-playing" placeholder={placeholder}>
      {ready ? data.items.map((item) => (
        <ShelfItem key={item.user.username}>
          <PlayerCard item={item} />
        </ShelfItem>
      )) : <PlayingSkeleton />}
    </GameShelf>
  );
}
