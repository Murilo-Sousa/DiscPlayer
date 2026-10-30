import { useEffect, useRef, useState } from "react";
import { useAsync } from "../hooks/useAsync.js";
import { STATUS_LABELS, STATUS_ORDER, formatDate } from "../utils/format.js";
import { GameCard } from "./GameCard.jsx";
import { GameGrid, GameGridSkeleton } from "./Layout.jsx";
import { Pagination } from "./Pagination.jsx";
import { EmptyState, ErrorState } from "./States.jsx";
import { Tabs, panelId } from "./Tabs.jsx";

// `only`: em quais abas a ordenação faz sentido. Quem está na fila ("Quero jogar") ainda não tem nota nem data de término,
// e só um jogo zerado tem data de término.
const SORTS = [
  { value: "recent", label: "Atualizados recentemente" },
  { value: "name", label: "Nome (A–Z)" },
  { value: "rating", label: "Maior nota", not: ["quero_jogar"] },
  { value: "completed", label: "Data de término", only: ["", "zerado"] },
];

const sortsFor = (status) =>
  SORTS.filter((item) => (!item.only || item.only.includes(status)) && !(item.not ?? []).includes(status));

function captionFor(entry) {
  let base = null;
  if (entry.status === "zerado" && entry.completed_at) base = `Zerado em ${formatDate(entry.completed_at)}`;
  else if (entry.status === "jogando" && entry.started_at) base = `Desde ${formatDate(entry.started_at)}`;
  else if (entry.status === "abandonado" && entry.status_changed_at) base = `Largado em ${formatDate(entry.status_changed_at)}`;
  else if (entry.status === "pausado" && entry.status_changed_at) base = `Pausado em ${formatDate(entry.status_changed_at)}`;
  if (entry.plays > 1) return base ? `${base} · ${entry.plays}ª jogada` : `${entry.plays}ª jogada`;
  return base;
}

/**
 * Biblioteca de jogos de uma pessoa (o diário, no caso de quem está logado): filtro por status,
 * favoritos, ordenação e paginação. `load(params, signal)` busca uma página.
 */
export function LibraryView({ load, scope, emptyAll, prefix = "library" }) {
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("recent");
  const [favorites, setFavorites] = useState(false);
  const [page, setPage] = useState(1);
  const counts = useRef(null);

  const state = useAsync(
    (signal) =>
      load({ status: status || undefined, sort, favorites: favorites ? 1 : undefined, page, per_page: 24 }, signal),
    [scope, status, sort, favorites, page],
  );
  useEffect(() => {
    if (state.data?.counts) counts.current = state.data.counts;
  }, [state.data]);

  const known = state.data?.counts ?? counts.current;
  const tabs = [
    { value: "", label: "Todos", count: known?.total },
    ...STATUS_ORDER.map((value) => ({ value, label: STATUS_LABELS[value], count: known?.[value] })),
  ];
  const change = (apply) => (value) => {
    apply(value);
    setPage(1);
  };
  const changeStatus = (value) => {
    if (value === "quero_jogar") setFavorites(false); // quem está na fila não tem favoritos
    if (!sortsFor(value).some((item) => item.value === sort)) setSort("recent"); // e a ordenação some junto com a aba
    change(setStatus)(value);
  };
  const queue = status === "quero_jogar";

  return (
    <div className="library">
      <Tabs tabs={tabs} value={status} onChange={changeStatus} label="Filtrar por status" prefix={prefix} className="tabs-scroll tabs-pills" />
      <div className="library-tools">
        {!queue && (
          <label className="check-inline">
            <input type="checkbox" checked={favorites} onChange={(event) => change(setFavorites)(event.target.checked)} />
            <span>Só favoritos{known ? ` (${known.favorites})` : ""}</span>
          </label>
        )}
        <div className="inline-select">
          <label htmlFor={`${prefix}-sort`}>Ordenar</label>
          <select id={`${prefix}-sort`} value={sort} onChange={(event) => change(setSort)(event.target.value)}>
            {sortsFor(status).map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div role="tabpanel" id={panelId(prefix, status)} aria-labelledby={`${prefix}-tab-${status}`}>
        {state.error && !state.data ? (
          <ErrorState error={state.error} onRetry={state.reload} />
        ) : !state.data ? (
          <GameGridSkeleton count={12} />
        ) : state.data.items.length === 0 ? (
          status || favorites ? (
            <EmptyState title="Nada por aqui" compact>
              Nenhum jogo {favorites ? "favorito " : ""}
              {status ? `com o status “${STATUS_LABELS[status]}”` : ""} até agora.
            </EmptyState>
          ) : (
            emptyAll
          )
        ) : (
          <div aria-busy={state.loading || undefined}>
            <GameGrid>
              {state.data.items.map((item) => (
                <GameCard
                  key={item.game.rawg_id}
                  game={item.game}
                  entry={item.entry}
                  rating={item.rating}
                  caption={captionFor(item.entry)}
                />
              ))}
            </GameGrid>
            <Pagination
              page={page}
              hasNext={state.data.has_next}
              label="Páginas do diário"
              onPage={(next) => {
                setPage(next);
                window.scrollTo({ top: 0 });
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
