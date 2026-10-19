import { useEffect, useState } from "react";
import { Avatar } from "../components/Avatar.jsx";
import { GameCard } from "../components/GameCard.jsx";
import { Icon } from "../components/Icon.jsx";
import { GameGrid, GameGridSkeleton, ListSkeleton, PageHeader, Section } from "../components/Layout.jsx";
import { ListCard } from "../components/ListCard.jsx";
import { ReviewCard } from "../components/ReviewCard.jsx";
import { EmptyState, ErrorState } from "../components/States.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link, useSearchParams } from "../router/index.jsx";
import { searchApi } from "../services/api.js";
import { userPath } from "../utils/format.js";

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const [text, setText] = useState(q);
  useEffect(() => setText(q), [q]);
  useDocumentTitle(q ? `Busca: ${q}` : "Buscar");

  const state = useAsync((signal) => (q.length >= 2 ? searchApi.search(q, { signal }) : Promise.resolve(null)), [q]);
  const data = state.data;
  const nothing = data && !data.games.items.length && !data.users.length && !data.lists.length && !data.reviews.length;

  return (
    <div className="container page">
      <PageHeader title="Buscar" lead="Jogos, jogadores, listas e reviews em um só lugar." />
      <form
        className="search-page-form"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setParams({ q: text.trim() });
        }}
      >
        <label htmlFor="search-page-q" className="sr-only">
          O que você procura?
        </label>
        <div className="input-icon">
          <Icon name="search" size={18} />
          <input id="search-page-q" type="search" value={text} maxLength={100} autoComplete="off" placeholder="Nome de jogo, jogador, lista…" onChange={(event) => setText(event.target.value)} />
        </div>
        <button type="submit" className="btn btn-primary">
          Buscar
        </button>
      </form>

      {q.length < 2 ? (
        <EmptyState title={q ? "Digite pelo menos 2 letras" : "Comece a digitar"} compact>
          Use o campo acima para procurar na plataforma.
        </EmptyState>
      ) : state.error && !data ? (
        <ErrorState error={state.error} onRetry={state.reload} />
      ) : !data ? (
        <>
          <GameGridSkeleton count={6} />
          <ListSkeleton rows={3} />
        </>
      ) : nothing ? (
        <EmptyState title={`Nada encontrado para “${q}”`}>Confira a grafia ou tente um termo mais curto.</EmptyState>
      ) : (
        <div className="search-results" aria-busy={state.loading || undefined}>
          <Section title="Jogos">
            {data.games.error ? (
              <ErrorState error={data.games.error} title="A busca de jogos está indisponível" compact />
            ) : data.games.items.length === 0 ? (
              <p className="muted">Nenhum jogo encontrado.</p>
            ) : (
              <>
                <GameGrid dense>
                  {data.games.items.map((game) => (
                    <GameCard key={game.rawg_id} game={game} />
                  ))}
                </GameGrid>
                <p className="section-foot">
                  <Link to={`/jogos?q=${encodeURIComponent(q)}`} className="section-link">
                    Ver todos no catálogo
                  </Link>
                </p>
              </>
            )}
          </Section>
          {data.users.length > 0 && (
            <Section title="Jogadores">
              <ul className="people">
                {data.users.map((user) => (
                  <li key={user.username}>
                    <Link to={userPath(user.username)} className="person">
                      <Avatar user={user} size={44} />
                      <span className="person-text">
                        <strong>{user.display_name}</strong>
                        <span>@{user.username}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Section>
          )}
          {data.lists.length > 0 && (
            <Section title="Listas">
              <div className="list-grid">
                {data.lists.map((list) => (
                  <ListCard key={list.id} list={list} />
                ))}
              </div>
            </Section>
          )}
          {data.reviews.length > 0 && (
            <Section title="Reviews">
              <div className="review-list">
                {data.reviews.map((review) => (
                  <ReviewCard key={review.id} review={review} showGame />
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}
