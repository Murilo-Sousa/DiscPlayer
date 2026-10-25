import { useState } from "react";
import { Avatar } from "../components/Avatar.jsx";
import { RatingDiscs, StatusDisc } from "../components/Disc.jsx";
import { FollowButton } from "../components/FollowButton.jsx";
import { GameCard } from "../components/GameCard.jsx";
import { LibraryView } from "../components/LibraryView.jsx";
import { ActivityList, GameGrid, Histogram, ListSkeleton, Section, Stat } from "../components/Layout.jsx";
import { ListCard } from "../components/ListCard.jsx";
import { Pagination } from "../components/Pagination.jsx";
import { ReviewCard } from "../components/ReviewCard.jsx";
import { Async, EmptyState, ErrorState, Loader } from "../components/States.jsx";
import { Tabs, panelId } from "../components/Tabs.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link, useParams, useSearchParams } from "../router/index.jsx";
import { usersApi } from "../services/api.js";
import {
  MONTH_LETTERS,
  MONTH_NAMES,
  RATING_LABELS,
  RATING_SR,
  STATUS_LABELS,
  STATUS_PROGRESS,
  formatAverage,
  formatMonthYear,
  plural,
  retrospectivePath,
  userPath,
} from "../utils/format.js";
import NotFoundPage from "./NotFoundPage.jsx";

function Summary({ profile, isSelf }) {
  const { stats, favorites, recent, user } = profile;
  const year = new Date().getFullYear();
  const empty = stats.games === 0 && stats.ratings === 0;
  if (empty) {
    return (
      <EmptyState title={isSelf ? "Seu perfil ainda está em branco" : `${user.display_name} ainda não registrou nada`} compact>
        {isSelf ? (
          <>
            Registre o primeiro jogo no <Link to="/jogos">catálogo</Link> e as estatísticas aparecem aqui.
          </>
        ) : (
          "Quando houver jogos e notas, as estatísticas aparecem aqui."
        )}
      </EmptyState>
    );
  }
  return (
    <div className="profile-summary">
      <dl className="stats-strip">
        <Stat value={stats.games} label="Jogos no diário" />
        <Stat value={stats.completed_this_year} label={`Zeradas em ${year}`} />
        <Stat value={stats.ratings} label="Notas dadas" hint={stats.reviews_with_text ? `${stats.reviews_with_text} com texto` : undefined} />
        <Stat value={formatAverage(stats.average_rating)} label="Média das notas" />
      </dl>

      {favorites.length > 0 && (
        <Section title="Favoritos">
          <GameGrid dense>
            {favorites.map((item) => (
              <GameCard key={item.game.rawg_id} game={item.game} entry={item.entry} rating={item.rating} />
            ))}
          </GameGrid>
        </Section>
      )}

      <div className="profile-charts">
        <Section title="Por status" headingLevel={2}>
          <ul className="status-bars">
            {STATUS_PROGRESS.map((status) => {
              const value = stats.by_status[status];
              const pct = stats.games ? (value / stats.games) * 100 : 0;
              return (
                <li key={status} data-status={status}>
                  <span className="status-bars-label">
                    <StatusDisc status={status} size={16} />
                    {STATUS_LABELS[status]}
                  </span>
                  <span className="status-bars-track" aria-hidden="true">
                    <span style={{ width: `${pct}%` }} />
                  </span>
                  <span className="status-bars-value">{value}</span>
                </li>
              );
            })}
          </ul>
        </Section>
        <Section title={`Zerados por mês em ${year}`}>
          <Histogram
            values={stats.completions_by_month}
            labels={MONTH_LETTERS}
            srLabels={MONTH_NAMES}
            caption={`Jogadas zeradas em cada mês de ${year}`}
            emptyText={`Nenhuma jogada zerada em ${year} até agora.`}
          />
        </Section>
        {stats.ratings > 0 && (
          <Section title="Distribuição das notas">
            <Histogram
              values={stats.rating_distribution}
              labels={RATING_LABELS}
              srLabels={RATING_SR}
              caption={`Notas dadas por ${user.display_name}`}
            />
          </Section>
        )}
      </div>

      {recent.length > 0 && (
        <Section title="Atualizados recentemente">
          <GameGrid dense>
            {recent.map((item) => (
              <GameCard key={item.game.rawg_id} game={item.game} entry={item.entry} rating={item.rating} />
            ))}
          </GameGrid>
        </Section>
      )}
    </div>
  );
}

function Paged({ fetchPage, scope, render, empty, skeleton = <ListSkeleton rows={4} />, label }) {
  const [page, setPage] = useState(1);
  const state = useAsync((signal) => fetchPage({ page, per_page: 20 }, signal), [scope, page]);
  return (
    <Async state={state} skeleton={skeleton} isEmpty={(data) => data.items.length === 0} empty={empty}>
      {(data) => (
        <>
          {render(data.items)}
          <Pagination page={page} hasNext={data.has_next} label={label} onPage={setPage} />
        </>
      )}
    </Async>
  );
}

function People({ users }) {
  return (
    <ul className="people">
      {users.map((person) => (
        <li key={person.username}>
          <Link to={userPath(person.username)} className="person">
            <Avatar user={person} size={44} />
            <span className="person-text">
              <strong>{person.display_name}</strong>
              <span>@{person.username}</span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function ProfilePage() {
  const { username } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("aba") ?? "resumo";
  const state = useAsync((signal) => usersApi.profile(username, { signal }), [username]);
  const profile = state.data;
  useDocumentTitle(profile ? `${profile.user.display_name} (@${profile.user.username})` : "Perfil");

  if (state.error && !profile) {
    if (state.error.status === 404) {
      return <NotFoundPage title="Perfil não encontrado">Não existe ninguém com o nome de usuário @{username}.</NotFoundPage>;
    }
    return (
      <div className="container page">
        <ErrorState error={state.error} onRetry={state.reload} />
      </div>
    );
  }
  if (!profile) {
    return (
      <div className="container page page-loading">
        <Loader label="Carregando o perfil" />
      </div>
    );
  }

  const { user, stats } = profile;
  const isSelf = profile.viewer.is_self;
  const name = user.username;

  const tabs = [
    { value: "resumo", label: "Resumo" },
    { value: "diario", label: "Diário", count: stats.games },
    { value: "reviews", label: "Reviews", count: stats.ratings },
    { value: "listas", label: "Listas", count: stats.lists },
    { value: "atividade", label: "Atividade" },
    { value: "seguidores", label: "Seguidores", count: stats.followers },
    { value: "seguindo", label: "Seguindo", count: stats.following },
  ];
  const current = tabs.some((item) => item.value === tab) ? tab : "resumo";
  const setTab = (value) => setParams(value === "resumo" ? {} : { aba: value }, { replace: true });

  const patchFollow = (result) =>
    state.setData((data) => ({
      ...data,
      viewer: { ...data.viewer, is_following: result.following },
      stats: { ...data.stats, followers: result.followers },
    }));

  let content;
  if (current === "resumo") content = <Summary profile={profile} isSelf={isSelf} />;
  else if (current === "diario") {
    content = (
      <LibraryView
        prefix="profile-library"
        scope={name}
        load={(query, signal) => usersApi.library(name, query, { signal })}
        emptyAll={<EmptyState title="Diário vazio" compact>{isSelf ? "Você ainda não registrou jogos." : `${user.display_name} ainda não registrou jogos.`}</EmptyState>}
      />
    );
  } else if (current === "reviews") {
    content = (
      <Paged
        scope={name}
        label="Páginas de reviews"
        fetchPage={(query, signal) => usersApi.reviews(name, query, { signal })}
        empty={<EmptyState title="Nenhuma review" compact>Notas e textos aparecem aqui.</EmptyState>}
        render={(items) => (
          <div className="review-list">
            {items.map((review) => (
              <ReviewCard key={review.id} review={review} showGame showAuthor={false} />
            ))}
          </div>
        )}
      />
    );
  } else if (current === "listas") {
    content = <ProfileLists username={name} isSelf={isSelf} />;
  } else if (current === "atividade") {
    content = (
      <Paged
        scope={name}
        label="Páginas de atividade"
        fetchPage={(query, signal) => usersApi.activity(name, query, { signal })}
        empty={<EmptyState title="Sem atividade" compact>O histórico aparece aqui conforme os jogos forem registrados.</EmptyState>}
        render={(items) => <ActivityList items={items} showUser={false} />}
      />
    );
  } else {
    const direction = current === "seguidores" ? "followers" : "following";
    content = (
      <Paged
        scope={`${name}-${direction}`}
        label="Páginas de pessoas"
        fetchPage={(query, signal) => usersApi[direction](name, query, { signal })}
        empty={
          <EmptyState title={direction === "followers" ? "Ninguém segue esta pessoa ainda" : "Não segue ninguém ainda"} compact />
        }
        render={(items) => <People users={items} />}
      />
    );
  }

  return (
    <div className="container page profile">
      <header className="profile-head">
        <Avatar user={user} size={96} className="profile-avatar" />
        <div className="profile-head-text">
          <h1 className="profile-name">{user.display_name}</h1>
          <p className="profile-handle">@{user.username}</p>
          {user.bio && <p className="profile-bio">{user.bio}</p>}
          <p className="profile-meta">
            {user.created_at && <span>No DiscPlayer desde {formatMonthYear(user.created_at)}</span>}
            {stats.average_rating !== null && (
              <span className="profile-avg">
                <RatingDiscs value={stats.average_rating} size={13} />
                média {formatAverage(stats.average_rating)} em {plural(stats.ratings, "nota", "notas")}
              </span>
            )}
          </p>
        </div>
        <div className="profile-actions">
          {isSelf ? (
            <Link to="/configuracoes" className="btn">
              Editar perfil
            </Link>
          ) : (
            <FollowButton username={user.username} following={profile.viewer.is_following} onChange={patchFollow} />
          )}
          {(stats.games > 0 || stats.ratings > 0) && (
            <Link to={retrospectivePath(user.username)} className="btn btn-quiet">
              Retrospectiva
            </Link>
          )}
        </div>
      </header>

      <Tabs tabs={tabs} value={current} onChange={setTab} label={`Seções do perfil de ${user.display_name}`} prefix="profile" className="tabs-scroll" />
      <div role="tabpanel" id={panelId("profile", current)} aria-labelledby={`profile-tab-${current}`} className="tab-panel">
        {content}
      </div>
    </div>
  );
}

function ProfileLists({ username, isSelf }) {
  const state = useAsync((signal) => usersApi.lists(username, { signal }), [username]);
  return (
    <Async
      state={state}
      skeleton={<ListSkeleton rows={3} />}
      isEmpty={(data) => data.items.length === 0}
      empty={
        <EmptyState
          title="Nenhuma lista"
          compact
          action={isSelf && <Link to="/listas?aba=minhas" className="btn btn-primary">Criar uma lista</Link>}
        >
          {isSelf ? "Agrupe jogos por tema, ano ou humor." : "Listas públicas aparecem aqui."}
        </EmptyState>
      }
    >
      {(data) => (
        <div className="list-grid">
          {data.items.map((list) => (
            <ListCard key={list.id} list={list} showOwner={false} />
          ))}
        </div>
      )}
    </Async>
  );
}
