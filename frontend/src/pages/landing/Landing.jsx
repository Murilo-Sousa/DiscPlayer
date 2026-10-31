import { useState } from "react";
import { Cover } from "../../components/Cover.jsx";
import { StatusDisc, Disc } from "../../components/Disc.jsx";
import { DemoBadge } from "../../components/DemoBadge.jsx";
import { Histogram } from "../../components/Layout.jsx";
import { ListCard } from "../../components/ListCard.jsx";
import { RankingList } from "../../components/Ranking.jsx";
import { RatingInput } from "../../components/RatingInput.jsx";
import { ReviewCard } from "../../components/ReviewCard.jsx";
import { Skeleton } from "../../components/States.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { Link } from "../../router/index.jsx";
import { gamesApi, listsApi, reviewsApi, usersApi } from "../../services/api.js";
import { gamePath, plural, retrospectivePath } from "../../utils/format.js";
import { DiscInstrument } from "./DiscInstrument.jsx";

const MONTH_LETTERS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const MONTH_NAMES = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

const WALL_COLUMNS = 3;
const WALL_SIZE = 15;
const WALL_MIN = 6;

/**
 * Os jogos do mural: os em alta primeiro, depois os lançamentos recentes, sem repetir e só com capa de verdade
 * (uma capa de iniciais num mural de capas parece um buraco).
 */
export function wallGames(featured) {
  const seen = new Set();
  const games = [];
  for (const game of [...(featured?.popular ?? []), ...(featured?.new ?? [])]) {
    if (!game?.cover_thumb_url && !game?.cover_url) continue;
    if (seen.has(game.rawg_id)) continue;
    seen.add(game.rawg_id);
    games.push(game);
  }
  return games.length >= WALL_MIN ? games.slice(0, WALL_SIZE) : [];
}

/** Reparte os jogos em colunas, um de cada vez, para cada coluna ter um pouco de tudo. */
export function wallColumns(games, columns = WALL_COLUMNS) {
  const result = Array.from({ length: columns }, () => []);
  games.forEach((game, index) => result[index % columns].push(game));
  return result;
}

/** Colunas de capas que sobem e descem bem devagar. Para o movimento quando a pessoa passa o mouse ou foca uma capa. */
function CoverWall({ games }) {
  const columns = wallColumns(games);
  return (
    <div className="landing-hero-art">
      <div className="cover-wall" role="group" aria-label="Jogos em alta agora">
        {columns.map((column, index) => (
          <ul key={index} className="cover-wall-col">
            {column.map((game) => (
              <li key={game.rawg_id}>
                <Link to={gamePath(game)} className="cover-wall-link">
                  <Cover game={game} ratio="poster" />
                  <span className="cover-wall-name">{game.name}</span>
                </Link>
              </li>
            ))}
          </ul>
        ))}
      </div>
      <p className="landing-fine cover-wall-caption">
        Em alta agora.{" "}
        <Link to="/jogos?ordering=popular" className="section-link">
          Ver o catálogo
        </Link>
      </p>
    </div>
  );
}

function CoverWallSkeleton() {
  return (
    <div className="landing-hero-art" aria-hidden="true">
      <div className="cover-wall">
        {Array.from({ length: WALL_COLUMNS }, (_, column) => (
          <ul key={column} className="cover-wall-col" data-loading>
            {Array.from({ length: 3 }, (_, row) => (
              <li key={row}>
                <Skeleton className="skeleton-cover" />
              </li>
            ))}
          </ul>
        ))}
      </div>
    </div>
  );
}

/** Título editorial e, ao lado, o mural de capas da RAWG. Sem a RAWG, o mural some e o título fica sozinho. */
function Hero() {
  const state = useAsync((signal) => gamesApi.featured({ signal }), []);
  const games = state.data ? wallGames(state.data) : [];
  const hasWall = !state.error && (!state.data || games.length > 0);
  return (
    <section className="landing-hero" data-wall={hasWall ? "on" : "off"} aria-labelledby="hero-title">
      <div className="landing-hero-copy">
        <h1 id="hero-title" className="landing-title">
          O diário de quem joga.
        </h1>
        <p className="landing-lead">
          Guarde o que você quer jogar, acompanhe o que está jogando e conte o que achou do que zerou. Depois veja o que
          outras pessoas andam jogando.
        </p>
        <div className="hero-actions">
          <Link to="/cadastro" className="btn btn-primary btn-lg">
            Criar meu diário
          </Link>
          <Link to="/jogos" className="btn btn-lg">
            Explorar jogos
          </Link>
        </div>
      </div>
      {hasWall && (state.data ? <CoverWall games={games} /> : <CoverWallSkeleton />)}
    </section>
  );
}

/** O disco grande, numa seção só dele: escolha um status e veja o que o diário libera. */
function DiscSection() {
  return (
    <section className="landing-section" aria-labelledby="disc-title">
      <h2 id="disc-title" className="landing-h2">
        Veja como o diário funciona
      </h2>
      <p className="landing-body">
        Cada status libera uma coisa diferente: datas, favorito, nota, jogar de novo. Escolha um e veja o disco fechar,
        junto com o que o diário passa a aceitar.
      </p>
      <DiscInstrument />
    </section>
  );
}

const JOURNEY = [
  {
    status: "quero_jogar",
    title: "Guarde na fila",
    text: "Marque o que você quer jogar, até o que ainda nem foi lançado. A fila não tem datas nem nota: é só uma promessa.",
  },
  {
    status: "jogando",
    title: "Comece a jogar",
    text: "Ao mudar para “Jogando”, a data de início já vem preenchida, e o diário mostra há quantos dias o jogo está com você.",
  },
  {
    status: "zerado",
    title: "Conte como foi",
    text: "Ao zerar, a data de término entra sozinha. Dê uma nota, escreva a review e avise se ela tem spoilers.",
  },
];

function Journey() {
  return (
    <section className="landing-section" aria-labelledby="journey-title">
      <h2 id="journey-title" className="landing-h2">
        Do “quero jogar” ao “zerei”
      </h2>
      <ol className="journey">
        {JOURNEY.map(({ status, title, text }) => (
          <li key={status} className="journey-step">
            <StatusDisc status={status} size={44} />
            <h3>{title}</h3>
            <p>{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function RatingSection() {
  const [value, setValue] = useState(7.5);
  return (
    <section className="landing-section landing-split" aria-labelledby="rating-title">
      <div className="landing-split-text">
        <h2 id="rating-title" className="landing-h2">
          Dez pontos, cinco discos
        </h2>
        <p className="landing-body">
          Cada disco vale dois pontos, e cada quarto de disco vale meio ponto. Por isso 7,5 e 8 são notas diferentes, e
          dá para dizer “quase um 9” sem arredondar.
        </p>
        <p className="landing-body">
          Só dá nota quem já começou o jogo. A média de um jogo no DiscPlayer vem de quem de fato o jogou.
        </p>
      </div>
      <div className="landing-split-demo">
        <div className="rating-demo">
          <p className="rating-demo-title">Mova o controle para ver a nota se montar</p>
          <RatingInput value={value} onChange={(next) => setValue(next ?? 7.5)} />
        </div>
      </div>
    </section>
  );
}

function Community({ reviews, hasExamples }) {
  const ranking = useAsync((signal) => gamesApi.topRated({ per_page: 5 }, { signal }), []);
  const items = reviews.data?.items ?? [];
  const showRanking = ranking.data && ranking.data.items.length > 0;
  if (reviews.error || (reviews.data && items.length === 0 && !showRanking)) {
    return (
      <section className="landing-section" aria-labelledby="community-title">
        <h2 id="community-title" className="landing-h2">
          A comunidade está começando
        </h2>
        <p className="landing-body">As reviews, as notas e as listas de quem entra aparecem aqui. A primeira pode ser a sua.</p>
        <Link to="/cadastro" className="btn btn-primary btn-lg">
          Criar meu diário
        </Link>
      </section>
    );
  }
  return (
    <section className="landing-section" aria-labelledby="community-title">
      <h2 id="community-title" className="landing-h2">
        O que a comunidade está escrevendo
      </h2>
      <div className="landing-community" data-with-ranking={showRanking || undefined}>
        <div className="review-list landing-reviews" data-grid>
          {!reviews.data
            ? Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="landing-review-skeleton" />)
            : items.slice(0, 4).map((review) => <ReviewCard key={review.id} review={review} showGame />)}
        </div>
        {showRanking && (
          <aside className="landing-ranking" aria-labelledby="ranking-title">
            <h3 id="ranking-title" className="landing-h3">
              Mais bem avaliados
            </h3>
            <RankingList items={ranking.data.items} />
            <p className="landing-fine">Um jogo entra aqui com notas de pelo menos {ranking.data.min_notes ?? 3} pessoas diferentes.</p>
          </aside>
        )}
      </div>
      {hasExamples && (
        <p className="landing-fine landing-example-note">
          Os perfis marcados como <DemoBadge user={{ is_demo: true }} /> são fictícios, criados para mostrar o site com atividade.
        </p>
      )}
    </section>
  );
}

function Lists() {
  const state = useAsync((signal) => listsApi.community({ per_page: 2 }, { signal }), []);
  const items = state.data?.items ?? [];
  return (
    <section className="landing-section landing-split" aria-labelledby="lists-title">
      <div className="landing-split-text">
        <h2 id="lists-title" className="landing-h2">
          Listas para dividir o que você ama
        </h2>
        <p className="landing-body">
          Junte jogos numa lista, ordene do seu jeito e mande o endereço para quem quiser. As públicas aparecem para toda a
          comunidade; as privadas ficam só com você.
        </p>
        <Link to="/listas" className="section-link">
          Ver as listas da comunidade
        </Link>
      </div>
      {items.length > 0 && (
        <div className="landing-split-demo">
          <div className="landing-lists">
            {items.map((list) => (
              <ListCard key={list.id} list={list} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

/** Quando há um perfil de exemplo, a retrospectiva dele (calculada de verdade) ilustra a seção. Contas reais nunca entram. */
function Year({ reviews }) {
  const example = reviews.data?.items.find((review) => review.user?.is_demo)?.user;
  const state = useAsync(
    (signal) => (example ? usersApi.retrospective(example.username, undefined, { signal }) : Promise.resolve(null)),
    [example?.username],
  );
  const data = state.data && !state.data.empty ? state.data : null;
  return (
    <section className="landing-section landing-split" aria-labelledby="year-title">
      <div className="landing-split-text">
        <h2 id="year-title" className="landing-h2">
          Seu ano em jogos
        </h2>
        <p className="landing-body">
          No fim do ano, a retrospectiva junta o que você zerou, começou, abandonou e jogou de novo, mês a mês, com o jogo
          do ano e uma imagem pronta para compartilhar.
        </p>
        <p className="landing-body">Tudo é calculado dos seus registros, sem estimativas.</p>
      </div>
      {data && (
        <div className="landing-split-demo">
          <figure className="year-demo">
            <p className="year-demo-number">
              <span>{data.totals.completed}</span> {data.totals.completed === 1 ? "jogo zerado" : "jogos zerados"} em {data.year}
            </p>
            <Histogram
              values={data.by_month}
              labels={MONTH_LETTERS}
              srLabels={MONTH_NAMES}
              caption={`Jogadas zeradas por mês em ${data.year}, no perfil de exemplo de ${data.user.display_name}`}
            />
            <figcaption>
              <Link to={retrospectivePath(data.user.username, data.year)}>
                Ver a retrospectiva de {data.user.display_name}
              </Link>
              <DemoBadge user={data.user} />
            </figcaption>
          </figure>
        </div>
      )}
    </section>
  );
}

const PRINCIPLES = [
  {
    title: "Quem avalia, jogou",
    text: "Só dá nota quem já começou o jogo. Um jogo que ainda não saiu fica na fila até o lançamento.",
  },
  {
    title: "Spoilers ficam escondidos",
    text: "Quem escreve marca a review com spoilers, e o texto só aparece para quem pedir.",
  },
  {
    title: "Média sem maquiagem",
    text: "A nota do DiscPlayer vem só das pessoas daqui, sempre com o número de avaliações. A da RAWG aparece à parte, com a fonte.",
  },
  {
    title: "Seus dados são seus",
    text: "Você exclui a conta quando quiser, e o diário, as notas e as listas saem junto.",
  },
];

function Principles() {
  return (
    <section className="landing-section" aria-labelledby="principles-title">
      <h2 id="principles-title" className="landing-h2">
        Um diário que não faz de conta
      </h2>
      <ul className="principles">
        {PRINCIPLES.map(({ title, text }) => (
          <li key={title}>
            <h3>{title}</h3>
            <p>{text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FinalCall() {
  return (
    <section className="landing-final" aria-labelledby="final-title">
      <div className="landing-final-text">
        <h2 id="final-title" className="landing-h2">
          Qual foi o último jogo que você terminou?
        </h2>
        <p className="landing-body">Registre-o agora e comece o seu diário por ele.</p>
        <div className="hero-actions">
          <Link to="/cadastro" className="btn btn-primary btn-lg">
            Criar meu diário
          </Link>
          <Link to="/entrar" className="btn btn-lg">
            Já tenho conta
          </Link>
        </div>
      </div>
      <Disc className="landing-final-disc" size={320} strokeScale={0.42} quarters={4} />
    </section>
  );
}

/** A página inicial de quem ainda não entrou: apresenta o produto, mostra a comunidade de verdade e convida a começar. */
export function Landing() {
  const reviews = useAsync((signal) => reviewsApi.recent({ per_page: 6 }, { signal }), []);
  const hasExamples = Boolean(reviews.data?.items.some((review) => review.user?.is_demo));
  return (
    <div className="landing">
      <Hero />
      <Journey />
      <DiscSection />
      <RatingSection />
      <Community reviews={reviews} hasExamples={hasExamples} />
      <Lists />
      <Year reviews={reviews} />
      <Principles />
      <FinalCall />
    </div>
  );
}
