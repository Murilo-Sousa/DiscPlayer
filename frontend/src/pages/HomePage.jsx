import { useState } from "react";
import { GameCard } from "../components/GameCard.jsx";
import { StatusDisc } from "../components/Disc.jsx";
import { ActivityList, GameGrid, GameGridSkeleton, ListSkeleton, Section } from "../components/Layout.jsx";
import { ReviewCard } from "../components/ReviewCard.jsx";
import { Async, EmptyState, ErrorState, Skeleton } from "../components/States.jsx";
import { Tabs, panelId } from "../components/Tabs.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link } from "../router/index.jsx";
import { feedApi, gamesApi, libraryApi, listsApi, reviewsApi } from "../services/api.js";
import { ListCard } from "../components/ListCard.jsx";
import {
  STATUS_LABELS,
  STATUS_PROGRESS,
  formatAverage,
  formatDate,
  formatYear,
  gamePath,
  playingFor,
  plural,
} from "../utils/format.js";
import { Cover } from "../components/Cover.jsx";

const STATUS_MEANING = {
  quero_jogar: "Na fila, ainda sem começar.",
  jogando: "Em andamento agora.",
  pausado: "Começou e deixou para depois.",
  zerado: "Terminou. O disco fecha o círculo.",
  abandonado: "Largou pelo caminho.",
};

/** Seis jogos em alta, como prateleira ao lado da apresentação. Sem a RAWG, a prateleira some e o resto fica. */
function HeroShelf({ state }) {
  const games = state.data?.popular?.slice(0, 6) ?? [];
  if (state.error || (state.data && games.length === 0)) return null;
  return (
    <div className="hero-shelf">
      <p className="hero-shelf-title">Em alta agora</p>
      <ul className="hero-tiles">
        {!state.data
          ? Array.from({ length: 6 }, (_, index) => (
              <li key={index} className="hero-tile" aria-hidden="true">
                <Skeleton className="skeleton-cover" />
              </li>
            ))
          : games.map((game) => (
              <li key={game.rawg_id} className="hero-tile">
                <Link to={gamePath(game)} className="hero-tile-link">
                  <Cover game={game} ratio="wide" />
                  <span className="hero-tile-name">{game.name}</span>
                </Link>
              </li>
            ))}
      </ul>
    </div>
  );
}

function Hero() {
  const featured = useAsync((signal) => gamesApi.featured({ signal }), []);
  const hasShelf = !featured.error && !(featured.data && !featured.data.popular?.length);
  return (
    <section className="hero" aria-labelledby="hero-title" data-solo={hasShelf ? undefined : true}>
      <div className="hero-copy">
        <p className="eyebrow">Diário e comunidade de videogames</p>
        <h1 id="hero-title" className="hero-title">
          O diário de quem joga.
        </h1>
        <p className="hero-lead">
          Anote o que você quer jogar, o que está jogando e o que zerou. Dê uma nota, escreva o que achou e veja o que
          outras pessoas andam jogando.
        </p>
        <div className="hero-actions">
          <Link to="/cadastro" className="btn btn-primary btn-lg">
            Começar meu diário
          </Link>
          <Link to="/jogos" className="btn btn-lg">
            Explorar jogos
          </Link>
        </div>
      </div>
      {hasShelf && <HeroShelf state={featured} />}
      <figure className="hero-legend">
        <figcaption className="hero-legend-title">Como o disco conta o seu jogo</figcaption>
        <ol className="legend-list">
          {STATUS_PROGRESS.map((status, index) => (
            <li key={status} className="legend-item" data-status={status} style={{ "--i": index }}>
              <StatusDisc status={status} size={34} />
              <span className="legend-text">
                <strong>{STATUS_LABELS[status]}</strong>
                <span>{STATUS_MEANING[status]}</span>
              </span>
            </li>
          ))}
        </ol>
      </figure>
    </section>
  );
}

function PlayingCard({ item }) {
  const { game, entry } = item;
  const since = entry.started_at ? `Desde ${formatDate(entry.started_at)}` : "Sem data de início";
  const span = playingFor(entry.started_at);
  return (
    <article className="playing-card">
      <Link to={gamePath(game)} className="playing-cover" tabIndex={-1} aria-hidden="true">
        <Cover game={game} ratio="poster" />
      </Link>
      <div className="playing-text">
        <Link to={gamePath(game)} className="playing-name">
          {game.name}
        </Link>
        <span className="playing-meta">
          <StatusDisc status="jogando" size={16} />
          <span>{since}</span>
        </span>
        {span && <span className="playing-span">{span}</span>}
      </div>
    </article>
  );
}

function PlayingNow({ user }) {
  const state = useAsync((signal) => libraryApi.mine({ status: "jogando", per_page: 4 }, { signal }), [user.username]);
  return (
    <Section
      title="Jogando agora"
      action={
        <Link to="/diario" className="section-link">
          Abrir meu diário
        </Link>
      }
    >
      <Async
        state={state}
        skeleton={<ListSkeleton rows={2} />}
        isEmpty={(data) => data.items.length === 0}
        empty={
          <EmptyState
            title="Nenhum jogo em andamento"
            compact
            action={
              <Link to="/jogos" className="btn btn-primary">
                Escolher um jogo
              </Link>
            }
          >
            Quando você marcar um jogo como “Jogando”, ele aparece aqui, com o tempo que você já dedicou a ele.
          </EmptyState>
        }
      >
        {(data) => (
          <div className="playing-list">
            {data.items.map((item) => (
              <PlayingCard key={item.game.rawg_id} item={item} />
            ))}
          </div>
        )}
      </Async>
    </Section>
  );
}

function UpNext({ user }) {
  const state = useAsync((signal) => libraryApi.mine({ status: "quero_jogar", per_page: 5 }, { signal }), [user.username]);
  return (
    <Section title="Na sua fila">
      <Async
        state={state}
        skeleton={<ListSkeleton rows={3} />}
        isEmpty={(data) => data.items.length === 0}
        empty={
          <EmptyState title="Sua fila está vazia" compact>
            Marque jogos como “Quero jogar” para guardar o que vem por aí.
          </EmptyState>
        }
      >
        {(data) => (
          <ul className="queue">
            {data.items.map(({ game }) => (
              <li key={game.rawg_id} className="queue-item">
                <Link to={gamePath(game)} className="ranking-cover" tabIndex={-1} aria-hidden="true">
                  <Cover game={game} ratio="poster" />
                </Link>
                <span className="ranking-text">
                  <Link to={gamePath(game)} className="ranking-name">
                    {game.name}
                  </Link>
                  {formatYear(game.released) && <span className="ranking-meta">{formatYear(game.released)}</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Async>
    </Section>
  );
}

function CommunityActivity({ user }) {
  const [tab, setTab] = useState("community");
  const community = useAsync((signal) => feedApi.community({ per_page: 6 }, { signal }), []);
  const following = useAsync(
    (signal) => (user ? feedApi.following({ per_page: 6 }, { signal }) : Promise.resolve(null)),
    [user?.username],
  );
  const active = tab === "following" && user ? following : community;

  const list = (
    <Async
      state={active}
      skeleton={<ListSkeleton rows={5} />}
      isEmpty={(data) => data.items.length === 0}
      empty={
        tab === "following" && user ? (
          <EmptyState title="Seu feed está vazio" compact>
            Siga outras pessoas para ver o que elas jogam e avaliam.{" "}
            <Link to="/buscar">Procurar jogadores</Link>
          </EmptyState>
        ) : (
          <EmptyState
            title="Ainda não há atividade"
            compact
            action={
              <Link to={user ? "/jogos" : "/cadastro"} className="btn btn-primary">
                {user ? "Registrar um jogo" : "Começar meu diário"}
              </Link>
            }
          >
            Quando alguém registrar um jogo, escrever uma review ou criar uma lista, aparece aqui. Que tal ser a primeira
            pessoa?
          </EmptyState>
        )
      }
    >
      {(data) => <ActivityList items={data.items} />}
    </Async>
  );

  return (
    <Section title="Na comunidade">
      {user && (
        <Tabs
          prefix="home-feed"
          label="Origem da atividade"
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "community", label: "Todos" },
            { value: "following", label: "Quem eu sigo" },
          ]}
        />
      )}
      <div role={user ? "tabpanel" : undefined} id={user ? panelId("home-feed", tab) : undefined} aria-labelledby={user ? `home-feed-tab-${tab}` : undefined}>
        {list}
      </div>
    </Section>
  );
}

function TopRated() {
  const state = useAsync((signal) => gamesApi.topRated({ per_page: 6 }, { signal }), []);
  return (
    <Section title="Mais bem avaliados pela comunidade">
      <Async state={state} skeleton={<ListSkeleton rows={4} />}>
        {(data) =>
          data.items.length === 0 ? (
            <EmptyState title="O ranking ainda está se formando" compact>
              Um jogo entra aqui quando {data.min_notes ?? 3} pessoas diferentes dão nota a ele. Que tal dar a sua?
            </EmptyState>
          ) : (
            <ol className="ranking">
              {data.items.map((item, index) => (
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
          )
        }
      </Async>
    </Section>
  );
}

function CommunityLists() {
  const state = useAsync((signal) => listsApi.community({ per_page: 2 }, { signal }), []);
  if (!state.data || state.data.items.length === 0) return null; // sem listas, a seção simplesmente não aparece
  return (
    <Section
      title="Listas da comunidade"
      action={
        <Link to="/listas" className="section-link">
          Ver todas
        </Link>
      }
    >
      <div className="home-lists">
        {state.data.items.map((list) => (
          <ListCard key={list.id} list={list} />
        ))}
      </div>
    </Section>
  );
}

function RecentReviews() {
  const state = useAsync((signal) => reviewsApi.recent({ per_page: 4 }, { signal }), []);
  return (
    <Section title="Reviews recentes">
      <Async
        state={state}
        skeleton={<ListSkeleton rows={3} />}
        isEmpty={(data) => data.items.length === 0}
        empty={
          <EmptyState title="Nenhuma review ainda" compact>
            As reviews escritas pela comunidade aparecem aqui.
          </EmptyState>
        }
      >
        {(data) => (
          <div className="review-list" data-grid>
            {data.items.map((review) => (
              <ReviewCard key={review.id} review={review} showGame />
            ))}
          </div>
        )}
      </Async>
    </Section>
  );
}

function Discover() {
  const [tab, setTab] = useState("popular");
  const state = useAsync((signal) => gamesApi.featured({ signal }), []);
  const games = state.data?.[tab];
  return (
    <Section
      title="Descobrir"
      action={
        <Link to={tab === "new" ? "/jogos?ordering=released" : "/jogos?ordering=popular"} className="section-link">
          Ver no catálogo
        </Link>
      }
    >
      <Tabs
        prefix="home-discover"
        label="Tipo de lista"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "popular", label: "Em alta" },
          { value: "new", label: "Lançamentos recentes" },
        ]}
      />
      <div role="tabpanel" id={panelId("home-discover", tab)} aria-labelledby={`home-discover-tab-${tab}`}>
        {state.error && !state.data ? (
          <ErrorState error={state.error} onRetry={state.reload} compact />
        ) : !state.data ? (
          <GameGridSkeleton count={6} />
        ) : state.data.errors?.[tab] ? (
          <ErrorState error={state.data.errors[tab]} title="Esta lista está indisponível" compact />
        ) : (
          <GameGrid dense>
            {games.slice(0, 6).map((game) => (
              <GameCard key={game.rawg_id} game={game} />
            ))}
          </GameGrid>
        )}
      </div>
    </Section>
  );
}

export default function HomePage() {
  useDocumentTitle("");
  const { user, ready } = useAuth();
  return (
    <div className="container page home">
      {ready && !user && <Hero />}
      {ready && user && (
        <>
          <h1 className="sr-only">Seu início no DiscPlayer</h1>
          <div className="home-columns home-top">
            <PlayingNow user={user} />
            <UpNext user={user} />
          </div>
        </>
      )}
      <div className="home-columns">
        <CommunityActivity user={user} />
        <div className="home-side">
          <TopRated />
          <CommunityLists />
        </div>
      </div>
      {user && <Discover />}
      <RecentReviews />
    </div>
  );
}
