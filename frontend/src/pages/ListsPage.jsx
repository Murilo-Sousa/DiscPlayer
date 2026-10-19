import { useEffect, useState } from "react";
import { Icon } from "../components/Icon.jsx";
import { ListFormDialog } from "../components/ListFormDialog.jsx";
import { ListSkeleton, PageHeader } from "../components/Layout.jsx";
import { ListCard } from "../components/ListCard.jsx";
import { Pagination } from "../components/Pagination.jsx";
import { Async, EmptyState } from "../components/States.jsx";
import { Tabs, panelId } from "../components/Tabs.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link, useNavigate, useSearchParams } from "../router/index.jsx";
import { listsApi } from "../services/api.js";
import { listPath } from "../utils/format.js";

function Community() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const page = Math.max(1, Number.parseInt(params.get("pagina") ?? "1", 10) || 1);
  const [text, setText] = useState(q);
  useEffect(() => setText(q), [q]);
  const state = useAsync((signal) => listsApi.community({ q: q || undefined, page, per_page: 18 }, { signal }), [q, page]);

  const go = (changes) =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      return next;
    });

  return (
    <>
      <form
        className="search-page-form"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          go({ q: text.trim(), pagina: "" });
        }}
      >
        <label htmlFor="lists-q" className="sr-only">
          Buscar listas
        </label>
        <div className="input-icon">
          <Icon name="search" size={18} />
          <input id="lists-q" type="search" value={text} maxLength={100} placeholder="Buscar listas pelo título ou descrição" onChange={(event) => setText(event.target.value)} />
        </div>
        <button type="submit" className="btn">
          Buscar
        </button>
      </form>
      <Async
        state={state}
        skeleton={<ListSkeleton rows={4} />}
        isEmpty={(data) => data.items.length === 0}
        empty={
          q ? (
            <EmptyState title={`Nenhuma lista para “${q}”`} compact />
          ) : (
            <EmptyState title="Ainda não há listas públicas" compact>
              Crie a primeira: agrupe jogos por tema, ano ou humor.
            </EmptyState>
          )
        }
      >
        {(data) => (
          <>
            <div className="list-grid">
              {data.items.map((list) => (
                <ListCard key={list.id} list={list} />
              ))}
            </div>
            <Pagination page={page} hasNext={data.has_next} label="Páginas de listas" onPage={(next) => go({ pagina: next > 1 ? String(next) : "" })} />
          </>
        )}
      </Async>
    </>
  );
}

function Mine({ onCreate }) {
  const state = useAsync((signal) => listsApi.mine({ signal }), []);
  return (
    <Async
      state={state}
      skeleton={<ListSkeleton rows={3} />}
      isEmpty={(data) => data.items.length === 0}
      empty={
        <EmptyState
          title="Você ainda não criou listas"
          action={
            <button type="button" className="btn btn-primary" onClick={onCreate}>
              Criar minha primeira lista
            </button>
          }
        >
          Listas guardam jogos por tema: “Para jogar em dupla”, “Os melhores de 2026”, “Curtos e bons”.
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

export default function ListsPage() {
  useDocumentTitle("Listas");
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = user && params.get("aba") === "minhas" ? "minhas" : "comunidade";
  const [creating, setCreating] = useState(false);

  return (
    <div className="container page">
      <PageHeader
        title="Listas"
        lead="Coleções de jogos montadas pela comunidade."
        actions={
          user ? (
            <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
              <Icon name="plus" size={18} />
              Nova lista
            </button>
          ) : (
            <Link to="/entrar?proximo=%2Flistas" className="btn">
              Entrar para criar listas
            </Link>
          )
        }
      />
      {user && (
        <Tabs
          prefix="lists"
          label="Origem das listas"
          value={tab}
          onChange={(value) => setParams(value === "minhas" ? { aba: "minhas" } : {}, { replace: true })}
          tabs={[
            { value: "comunidade", label: "Comunidade" },
            { value: "minhas", label: "Minhas listas" },
          ]}
        />
      )}
      <div role={user ? "tabpanel" : undefined} id={user ? panelId("lists", tab) : undefined} aria-labelledby={user ? `lists-tab-${tab}` : undefined} className="tab-panel">
        {tab === "minhas" ? <Mine onCreate={() => setCreating(true)} /> : <Community />}
      </div>
      <ListFormDialog open={creating} onClose={() => setCreating(false)} onSaved={(list) => navigate(listPath(list.id))} />
    </div>
  );
}
