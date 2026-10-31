import { useState } from "react";
import { Avatar } from "../components/Avatar.jsx";
import { RatingDiscs } from "../components/Disc.jsx";
import { Cover } from "../components/Cover.jsx";
import { GameCard } from "../components/GameCard.jsx";
import { GameGrid, Histogram, Section, Stat } from "../components/Layout.jsx";
import { EmptyState, ErrorState, Loader } from "../components/States.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link, useParams } from "../router/index.jsx";
import { usersApi } from "../services/api.js";
import { ApiError, assetUrl } from "../services/http.js";
import {
  MONTH_LETTERS,
  MONTH_NAMES,
  RATING_LABELS,
  RATING_SR,
  daysText,
  formatAverage,
  formatDate,
  formatRating,
  gamePath,
  isYearParam,
  plural,
  retrospectiveImagePath,
  retrospectivePath,
  userPath,
} from "../utils/format.js";
import { shareLink } from "../utils/share.js";
import NotFoundPage from "./NotFoundPage.jsx";
import { DemoBadge } from "../components/DemoBadge.jsx";

/**
 * O número em destaque da imagem de compartilhamento: o primeiro destes que existe. É a mesma ordem
 * que `retrospective_card` (backend/app/services/cards.py) usa para desenhar a imagem.
 */
export function headline(data) {
  const { totals, ratings } = data;
  if (totals.completed) return plural(totals.completed, "jogo zerado", "jogos zerados");
  if (totals.started) return plural(totals.started, "jogo começado", "jogos começados");
  if (ratings.count) return plural(ratings.count, "nota dada", "notas dadas");
  if (totals.abandoned) return plural(totals.abandoned, "jogo abandonado", "jogos abandonados");
  return plural(totals.replays, "recomeço", "recomeços");
}

/** O texto que acompanha o link ao compartilhar. Só usa números que a página mostra. */
export function shareText(data, isSelf) {
  const completed = data.totals.completed;
  const owner = isSelf ? "Minha retrospectiva" : `Retrospectiva de ${data.user.display_name}`;
  const base = `${owner} ${data.year} no DiscPlayer`;
  return completed > 0 ? `${base}: ${plural(completed, "jogo zerado", "jogos zerados")}.` : `${base}.`;
}

function YearNav({ username, years, current }) {
  // Com um único ano, e ele já aberto, não há para onde ir.
  if (years.length === 0 || (years.length === 1 && years[0] === current)) return null;
  const shown = years.includes(current) ? years : [current, ...years].sort((a, b) => b - a);
  return (
    <nav className="year-nav" aria-label="Anos com registros">
      <ul>
        {shown.map((year) => (
          <li key={year}>
            <Link
              to={retrospectivePath(username, year)}
              className="year-link"
              aria-current={year === current ? "page" : undefined}
            >
              {year}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function ShareButton({ data, isSelf, url }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const share = async () => {
    if (busy) return;
    setBusy(true);
    const result = await shareLink({
      url,
      title: `Retrospectiva ${data.year} de ${data.user.display_name} · DiscPlayer`,
      text: shareText(data, isSelf),
    });
    setBusy(false);
    if (result === "copied") toast.success("Endereço copiado. É só colar onde quiser compartilhar.");
    else if (result === "failed") toast.error("Não foi possível copiar o endereço. Copie-o pela barra do navegador.");
  };
  return (
    // aria-disabled (e não disabled): o botão continua focável, então o foco do teclado não se perde ao compartilhar.
    <button type="button" className="btn btn-primary" onClick={share} aria-disabled={busy || undefined}>
      Compartilhar
    </button>
  );
}

function Hero({ totals, year }) {
  const { completed, completed_games: games } = totals;
  return (
    <section className="retro-hero" aria-labelledby="retro-hero-title">
      <h2 id="retro-hero-title" className="sr-only">
        Resumo de {year}
      </h2>
      {completed > 0 ? (
        <>
          <p className="retro-big">
            <span className="retro-big-number">{completed}</span>
            <span className="retro-big-label">{completed === 1 ? "jogo zerado" : "jogos zerados"}</span>
          </p>
          {games !== completed && (
            <p className="retro-note">
              {plural(games, "jogo diferente", "jogos diferentes")}: alguns foram zerados mais de uma vez.
            </p>
          )}
        </>
      ) : (
        <p className="retro-none">Nenhum jogo zerado em {year}.</p>
      )}
      <dl className="stats-strip">
        <Stat value={totals.started} label="Começados" />
        <Stat value={totals.abandoned} label="Abandonados" />
        <Stat value={totals.replays} label="Jogados de novo" />
      </dl>
    </section>
  );
}

function MonthsSection({ data }) {
  const { by_month: months, busiest_month: busiest, year } = data;
  return (
    <Section title={`Zerados por mês em ${year}`}>
      <Histogram
        values={months}
        labels={MONTH_LETTERS}
        srLabels={MONTH_NAMES}
        caption={`Jogadas zeradas em cada mês de ${year}`}
        emptyText={`Nenhuma jogada zerada em ${year}.`}
      />
      {busiest !== null && (
        <p className="retro-note">
          Mês mais cheio: {MONTH_NAMES[busiest - 1]}, com {plural(months[busiest - 1], "zerado", "zerados")}.
        </p>
      )}
    </Section>
  );
}

function GameOfTheYear({ item, year }) {
  const { game } = item;
  return (
    <Section title={`Jogo de ${year}`}>
      <article className="retro-goty">
        <Link to={gamePath(game)} className="retro-goty-cover" tabIndex={-1} aria-hidden="true">
          <Cover game={game} ratio="poster" />
        </Link>
        <div className="retro-goty-text">
          <h3 className="retro-goty-name">
            <Link to={gamePath(game)}>{game.name}</Link>
          </h3>
          <p className="retro-goty-rating">
            <RatingDiscs value={item.rating} size={16} />
            <span aria-hidden="true">{formatRating(item.rating)}</span>
          </p>
          <p className="retro-note">
            Zerado em {formatDate(item.completed_at)}
            {item.times > 1 && `, ${item.times} vezes no ano`}
            {item.days !== null && item.times === 1 && ` (${daysText(item.days)})`}.
          </p>
          <p className="retro-note">Entre os zerados do ano, o de maior nota. Em caso de empate, o zerado mais recentemente.</p>
        </div>
      </article>
    </Section>
  );
}

/** Duas linhas sob a capa: a nota (quando há) e a data com a duração. */
function Caption({ item }) {
  const when = [formatDate(item.completed_at)];
  if (item.times > 1) when.push(`${item.times} vezes`);
  else if (item.days !== null) when.push(daysText(item.days));
  const hasRating = item.rating !== null && item.rating !== undefined;
  return (
    <>
      {hasRating && <span className="retro-cap">Nota {formatRating(item.rating)}</span>}
      <span className="retro-cap">{when.filter(Boolean).join(" · ")}</span>
    </>
  );
}

function CompletedSection({ data }) {
  const { completed_games: items, totals, year } = data;
  if (items.length === 0) return null;
  return (
    <Section title={`Zerados em ${year}`}>
      <GameGrid dense>
        {items.map((item) => (
          <GameCard key={item.game.rawg_id} game={item.game} caption={<Caption item={item} />} showYear={false} />
        ))}
      </GameGrid>
      {totals.completed_games > items.length && (
        <p className="retro-note">
          Mostrando {items.length} de {totals.completed_games} jogos, dos de maior nota para os sem nota.
        </p>
      )}
    </Section>
  );
}

function PaceSection({ pace }) {
  if (!pace) return null;
  const gameLink = (entry) => <Link to={gamePath(entry.game)}>{entry.game.name}</Link>;
  return (
    <Section title="Ritmo">
      <dl className="stats-strip">
        <Stat value={`${formatAverage(pace.average_days)} dias`} label="Média por jogo" />
        <Stat value={daysText(pace.fastest.days)} label="Mais rápido" hint={gameLink(pace.fastest)} />
        <Stat value={daysText(pace.longest.days)} label="Mais longo" hint={gameLink(pace.longest)} />
      </dl>
      <p className="retro-note">Só entram jogos zerados com data de início e de término.</p>
    </Section>
  );
}

function RatingsSection({ ratings, user }) {
  if (ratings.count === 0) return null;
  return (
    <Section title="Notas dadas">
      <dl className="stats-strip">
        <Stat value={ratings.count} label={ratings.count === 1 ? "Nota" : "Notas"} />
        <Stat value={formatAverage(ratings.average)} label="Média" />
        <Stat value={ratings.with_text} label="Com texto" />
      </dl>
      <Histogram
        values={ratings.distribution}
        labels={RATING_LABELS}
        srLabels={RATING_SR}
        caption={`Notas dadas por ${user.display_name} no ano`}
      />
    </Section>
  );
}

function CommunitySection({ social }) {
  if (social.likes_received + social.new_followers + social.lists_created === 0) return null;
  return (
    <Section title="Na comunidade">
      <dl className="stats-strip">
        <Stat value={social.likes_received} label={social.likes_received === 1 ? "Curtida recebida" : "Curtidas recebidas"} />
        <Stat value={social.new_followers} label={social.new_followers === 1 ? "Novo seguidor" : "Novos seguidores"} />
        <Stat value={social.lists_created} label={social.lists_created === 1 ? "Lista pública criada" : "Listas públicas criadas"} />
      </dl>
    </Section>
  );
}

function ShareImage({ data }) {
  const [failed, setFailed] = useState(false);
  const { user, year } = data;
  const src = assetUrl(retrospectiveImagePath(user.username, year));
  return (
    <Section title="Imagem para compartilhar">
      {failed ? (
        <p className="retro-note">Não foi possível carregar a imagem agora. O botão Compartilhar continua funcionando.</p>
      ) : (
        <figure className="retro-card">
          <img
            src={src}
            width="1200"
            height="630"
            loading="lazy"
            alt={`Imagem de compartilhamento: Retrospectiva ${year} de ${user.display_name}, ${headline(data)}`}
            onError={() => setFailed(true)}
          />
          <figcaption>
            É esta imagem que aparece quando o link da retrospectiva é colado em outros aplicativos.
          </figcaption>
        </figure>
      )}
      <p className="section-foot">
        <a className="btn" href={src} download={`retrospectiva-${year}-${user.username}.png`}>
          Baixar imagem
        </a>
      </p>
    </Section>
  );
}

function HowItWorks({ year }) {
  return (
    <details className="retro-how">
      <summary>Como esses números são calculados</summary>
      <ul>
        <li>Zerados: jogadas marcadas como zeradas com data de término em {year}. Zerar o mesmo jogo duas vezes no ano conta duas vezes.</li>
        <li>Começados: jogadas com data de início em {year}.</li>
        <li>Abandonados e jogados de novo: vêm do histórico do diário.</li>
        <li>
          Notas, curtidas e seguidores: contados pelo dia em que aconteceram, em horário UTC. Algo feito na virada do ano pode
          cair no ano vizinho.
        </li>
        <li>O DiscPlayer não guarda gêneros nem horas jogadas, então eles não aparecem aqui.</li>
        <li>Só dados públicos entram: listas privadas ficam de fora.</li>
      </ul>
    </details>
  );
}

/** A retrospectiva já carregada. Separada da busca de dados para poder ser renderizada em testes. */
export function RetrospectiveView({ data, isSelf, shareUrl }) {
  const { user, year, totals } = data;
  return (
    <div className="container page retro">
      <header className="retro-head">
        <Link to={userPath(user.username)} className="retro-owner">
          <Avatar user={user} size={28} />
          <span>{user.display_name}</span>
          <DemoBadge user={user} />
          <span className="retro-handle">@{user.username}</span>
        </Link>
        <h1 className="retro-title">
          Retrospectiva <span className="retro-year">{year}</span>
        </h1>
        {data.partial && <p className="retro-note">{year} ainda está em andamento: os números vão até hoje.</p>}
        {!data.empty && (
          <div className="retro-actions">
            <ShareButton data={data} isSelf={isSelf} url={shareUrl} />
          </div>
        )}
      </header>

      <YearNav username={user.username} years={data.years} current={year} />

      {data.empty ? (
        <EmptyState
          level={2}
          title={`Nada registrado em ${year}`}
          action={
            isSelf && (
              <Link to="/jogos" className="btn btn-primary">
                Adicionar jogos
              </Link>
            )
          }
        >
          {isSelf
            ? "Quando você registrar jogos, datas de início e término ou notas neste ano, a retrospectiva aparece aqui."
            : `${user.display_name} não registrou nada em ${year}.`}
        </EmptyState>
      ) : (
        <>
          <div className="retro-top" data-solo={data.game_of_the_year ? undefined : true}>
            <Hero totals={totals} year={year} />
            {data.game_of_the_year && <GameOfTheYear item={data.game_of_the_year} year={year} />}
          </div>
          <div className="retro-grid">
            <div className="retro-col">
              {totals.completed > 0 && <MonthsSection data={data} />}
              <CompletedSection data={data} />
              <PaceSection pace={data.pace} />
            </div>
            <div className="retro-col">
              <RatingsSection ratings={data.ratings} user={user} />
              <CommunitySection social={data.social} />
              <ShareImage data={data} />
            </div>
          </div>
          <HowItWorks year={year} />
        </>
      )}
    </div>
  );
}

export default function RetrospectivePage() {
  const { username, year } = useParams();
  const { user: viewer } = useAuth();
  const validYear = year === undefined || isYearParam(year);
  const state = useAsync(
    (signal) =>
      validYear
        ? usersApi.retrospective(username, year, { signal })
        : Promise.reject(new ApiError({ status: 404, code: "not_found" })),
    [username, year],
  );
  const data = state.data;
  useDocumentTitle(data ? `Retrospectiva ${data.year} de ${data.user.display_name}` : "Retrospectiva");

  if (state.error && !data) {
    if (state.error.status === 404) {
      return (
        <NotFoundPage title="Retrospectiva não encontrada">
          Não existe uma retrospectiva neste endereço. Confira o nome de usuário e o ano.
        </NotFoundPage>
      );
    }
    return (
      <div className="container page">
        <ErrorState error={state.error} onRetry={state.reload} />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="container page page-loading">
        <Loader label="Carregando a retrospectiva" />
      </div>
    );
  }

  const shareUrl = `${window.location.origin}${retrospectivePath(data.user.username, data.year)}`;
  return <RetrospectiveView data={data} isSelf={viewer?.username === data.user.username} shareUrl={shareUrl} />;
}
