import { useState } from "react";
import { LibraryView } from "../components/LibraryView.jsx";
import { ActivityList, ListSkeleton, PageHeader, Stat } from "../components/Layout.jsx";
import { Pagination } from "../components/Pagination.jsx";
import { Async, EmptyState } from "../components/States.jsx";
import { Tabs, panelId } from "../components/Tabs.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link } from "../router/index.jsx";
import { libraryApi, usersApi } from "../services/api.js";
import { formatAverage, plural, userPath } from "../utils/format.js";

function History({ username }) {
  const [page, setPage] = useState(1);
  const state = useAsync((signal) => usersApi.activity(username, { page, per_page: 20 }, { signal }), [username, page]);
  return (
    <Async
      state={state}
      skeleton={<ListSkeleton rows={6} />}
      isEmpty={(data) => data.items.length === 0}
      empty={
        <EmptyState title="O histórico começa no primeiro jogo" compact>
          Cada mudança de status, review e lista criada fica registrada aqui, em ordem.
        </EmptyState>
      }
    >
      {(data) => (
        <>
          <ActivityList items={data.items} showUser={false} />
          <Pagination page={page} hasNext={data.has_next} label="Páginas do histórico" onPage={setPage} />
        </>
      )}
    </Async>
  );
}

export default function DiaryPage() {
  useDocumentTitle("Meu diário");
  const { user } = useAuth();
  const [tab, setTab] = useState("games");
  const summary = useAsync((signal) => usersApi.profile(user.username, { signal }), [user.username]);
  const stats = summary.data?.stats;

  return (
    <div className="container page">
      <PageHeader
        title="Meu diário"
        lead="O que você quer jogar, está jogando, zerou, pausou ou largou."
        actions={
          <>
            <Link to="/jogos" className="btn btn-primary">
              Adicionar jogos
            </Link>
            <Link to={userPath(user.username)} className="btn">
              Ver perfil público
            </Link>
          </>
        }
      />
      {stats && stats.games > 0 && (
        <dl className="stats-strip">
          <Stat value={stats.games} label="Jogos no diário" />
          <Stat value={stats.by_status.jogando} label="Jogando agora" />
          <Stat value={stats.completed_this_year} label={`Zerados em ${new Date().getFullYear()}`} />
          <Stat value={formatAverage(stats.average_rating)} label="Média das suas notas" hint={stats.ratings ? plural(stats.ratings, "nota", "notas") : undefined} />
        </dl>
      )}
      <Tabs
        prefix="diary"
        label="Seções do diário"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "games", label: "Jogos" },
          { value: "history", label: "Histórico" },
        ]}
      />
      <div role="tabpanel" id={panelId("diary", tab)} aria-labelledby={`diary-tab-${tab}`} className="tab-panel">
        {tab === "games" ? (
          <LibraryView
            prefix="diary-library"
            scope={user.username}
            load={(params, signal) => libraryApi.mine(params, { signal })}
            emptyAll={
              <EmptyState
                title="Seu diário está vazio"
                action={
                  <Link to="/jogos" className="btn btn-primary">
                    Procurar um jogo
                  </Link>
                }
              >
                Abra a página de qualquer jogo e escolha um status para começar o registro.
              </EmptyState>
            }
          />
        ) : (
          <History username={user.username} />
        )}
      </div>
    </div>
  );
}
