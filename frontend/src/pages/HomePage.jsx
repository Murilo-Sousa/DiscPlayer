import { useState } from "react";
import { GameCard } from "../components/GameCard.jsx";
import { StatusDisc } from "../components/Disc.jsx";
import { ActivityList, GameGrid, GameGridSkeleton, ListSkeleton, Section } from "../components/Layout.jsx";
import { ReviewCard } from "../components/ReviewCard.jsx";
import { Async, EmptyState, ErrorState } from "../components/States.jsx";
import { Tabs, panelId } from "../components/Tabs.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link } from "../router/index.jsx";
import { feedApi, gamesApi, libraryApi, reviewsApi } from "../services/api.js";
import { STATUS_LABELS, STATUS_PROGRESS, formatAverage, gamePath, plural } from "../utils/format.js";
import { Cover } from "../components/Cover.jsx";

const STATUS_MEANING = {
  quero_jogar: "Na fila, ainda sem começar.",
  jogando: "Em andamento agora.",
  pausado: "Começou e deixou para depois.",
  zerado: "Terminou. O disco fecha o círculo.",
  abandonado: "Largou pelo caminho.",
};

function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
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

function PlayingNow({ user }) {
  const state = useAsync((signal) => libraryApi.mine({ status: "jogando", per_page: 6 }, { signal }), [user.username]);
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
        skeleton={<GameGridSkeleton count={6} />}
        isEmpty={(data) => data.items.length === 0}
        empty={
          <EmptyState
            title="Nenhum jogo em andamento"
            action={
              <Link to="/jogos" className="btn btn-primary">
                Escolher um jogo
              </Link>
            }
          >
            Quando você marcar um jogo como “Jogando”, ele aparece aqui.
          </EmptyState>
        }
      >
        {(data) => (
          <GameGrid dense>
            {data.items.map((item) => (
              <GameCard key={item.game.rawg_id} game={item.game} entry={item.entry} rating={item.rating} />
            ))}
          </GameGrid>
        )}
      </Async>
    </Section>
  );
}

function CommunityActivity({ user }) {
  const [tab, setTab] = useState("community");
  const community = useAsync((signal) => feedApi.community({ per_page: 10 }, { signal }), []);
  const following = useAsync(
    (signal) => (user ? feedApi.following({ per_page: 10 }, { signal }) : Promise.resolve(null)),
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
      <Async
        state={state}
        skeleton={<ListSkeleton rows={4} />}
        isEmpty={(data) => data.items.length === 0}
        empty={
          <EmptyState title="Ainda sem notas" compact>
            O ranking aparece quando as primeiras reviews forem publicadas.
          </EmptyState>
        }
      >
        {(data) => (
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
        )}
      </Async>
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
          <div className="review-list">
            {data.items.map((review) => (
              <ReviewCard key={review.id} review={review} showGame />
            ))}
          </div>
        )}
      </Async>
    </Section>
  );
}

function Featured() {
  const state = useAsync((signal) => gamesApi.featured({ signal }), []);
  const block = (key, title) => (
    <Section
      title={title}
      action={
        <Link to={key === "new" ? "/jogos?ordering=released" : "/jogos?ordering=popular"} className="section-link">
          Ver no catálogo
        </Link>
      }
    >
      {state.error && !state.data ? (
        <ErrorState error={state.error} onRetry={state.reload} compact />
      ) : !state.data ? (
        <GameGridSkeleton count={6} />
      ) : state.data.errors?.[key] ? (
        <ErrorState error={state.data.errors[key]} title="Esta lista está indisponível" compact />
      ) : (
        <GameGrid dense>
          {state.data[key].slice(0, 6).map((game) => (
            <GameCard key={game.rawg_id} game={game} />
          ))}
        </GameGrid>
      )}
    </Section>
  );
  return (
    <>
      {block("popular", "Em alta")}
      {block("new", "Lançamentos recentes")}
    </>
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
          <PlayingNow user={user} />
        </>
      )}
      <div className="home-columns">
        <CommunityActivity user={user} />
        <TopRated />
      </div>
      <Featured />
      <RecentReviews />
    </div>
  );
}
