import { useEffect, useState } from "react";
import { GameCard } from "../components/GameCard.jsx";
import { GameGrid, GameGridSkeleton, ListSkeleton, Section } from "../components/Layout.jsx";
import { ReviewCard } from "../components/ReviewCard.jsx";
import { Async, EmptyState, ErrorState, Loader } from "../components/States.jsx";
import { Tabs, panelId } from "../components/Tabs.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link } from "../router/index.jsx";
import { feedApi, gamesApi, listsApi, reviewsApi } from "../services/api.js";
import { ListCard } from "../components/ListCard.jsx";
import { RankingList } from "../components/Ranking.jsx";
import { Landing } from "./landing/Landing.jsx";
import { Highlights } from "./home/Highlights.jsx";
import { PlayingRail, SCOPES } from "./home/PlayingRail.jsx";

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
            <RankingList items={data.items} />
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
        <Link to={tab === "new" ? "/jogos?ordem=released" : "/jogos?ordem=popular"} className="section-link">
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
              <GameCard key={game.igdb_id} game={game} />
            ))}
          </GameGrid>
        )}
      </div>
    </Section>
  );
}

const SCOPE_KEY = "discplayer.home-scope";

function savedScope() {
  try {
    const value = window.localStorage.getItem(SCOPE_KEY);
    return SCOPES.some((scope) => scope.value === value) ? value : "following";
  } catch {
    return "following"; // sem armazenamento (janela privada, por exemplo): vale o padrão
  }
}

/**
 * O início de quem está logado: quem joga o quê agora e as novidades, da comunidade ou de quem a pessoa segue.
 * A escolha vale para as duas partes e fica guardada neste navegador. Quem não segue ninguém começa na comunidade.
 */
function HomeBoard() {
  const [scope, setScope] = useState(savedScope);
  const [touched, setTouched] = useState(false);
  const playing = useAsync((signal) => feedApi.playing(scope, { per_page: 12 }, { signal }), [scope]);
  const news = useAsync((signal) => feedApi.highlights(scope, { per_page: 10 }, { signal }), [scope]);

  useEffect(() => {
    if (!touched && scope === "following" && playing.data?.scope === "following" && playing.data.following === 0) {
      setScope("community");
    }
  }, [touched, scope, playing.data]);

  const choose = (next) => {
    setTouched(true);
    setScope(next);
    try {
      window.localStorage.setItem(SCOPE_KEY, next);
    } catch {
      /* só uma conveniência: sem armazenamento, a escolha vale até recarregar */
    }
  };
  return (
    <>
      <PlayingRail data={playing.data} scope={scope} error={playing.error} onRetry={playing.reload} onScope={choose} />
      <div className="home-columns">
        <Highlights data={news.data} scope={scope} error={news.error} onRetry={news.reload} />
        <div className="home-side">
          <TopRated />
          <CommunityLists />
        </div>
      </div>
    </>
  );
}

export default function HomePage() {
  useDocumentTitle("");
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <div className="container page page-loading">
        <Loader label="Carregando o início" />
      </div>
    );
  }
  // Quem ainda não entrou vê a apresentação do DiscPlayer (com a comunidade real dentro dela).
  if (!user) {
    return (
      <div className="container page home">
        <Landing />
      </div>
    );
  }
  return (
    <div className="container page home">
      <h1 className="sr-only">Seu início no DiscPlayer</h1>
      <HomeBoard />
      <Discover />
      <RecentReviews />
    </div>
  );
}
