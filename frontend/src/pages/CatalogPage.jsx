import { useEffect, useState } from "react";
import { GameCard } from "../components/GameCard.jsx";
import { GameGrid, GameGridSkeleton, PageHeader } from "../components/Layout.jsx";
import { Pagination } from "../components/Pagination.jsx";
import { EmptyState, ErrorState } from "../components/States.jsx";
import { Icon } from "../components/Icon.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDebounced } from "../hooks/useDebounced.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { useSearchParams } from "../router/index.jsx";
import { gamesApi } from "../services/api.js";

const PER_PAGE = 24;
const MAX_PAGES = 400; // a RAWG limita a paginação profunda

const ORDERINGS = [
  { value: "relevance", label: "Relevância" },
  { value: "popular", label: "Mais populares" },
  { value: "released", label: "Lançamento mais recente" },
  { value: "rating", label: "Melhor avaliação (RAWG)" },
  { value: "metacritic", label: "Metacritic" },
  { value: "name", label: "Nome (A–Z)" },
];

const thisYear = new Date().getFullYear();
const YEARS = Array.from({ length: thisYear + 1 - 1990 + 1 }, (_, index) => thisYear + 1 - index);

export default function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const genre = params.get("genero") ?? "";
  const platform = params.get("plataforma") ?? "";
  const year = params.get("ano") ?? "";
  const ordering = params.get("ordem") ?? "";
  const page = Math.max(1, Number.parseInt(params.get("pagina") ?? "1", 10) || 1);

  useDocumentTitle(q ? `Jogos: ${q}` : "Jogos");

  const [text, setText] = useState(q);
  const debounced = useDebounced(text, 350);
  // Se a URL mudar por fora (voltar/avançar), o campo acompanha.
  useEffect(() => setText(q), [q]);
  useEffect(() => {
    if (debounced.trim() !== q) update({ q: debounced.trim() }, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const update = (changes, replace = false) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries({ pagina: "", ...changes })) {
          if (value) next.set(key, value);
          else next.delete(key);
        }
        return next;
      },
      { replace },
    );
  };
  const urlKeys = { q: "q", genre: "genero", platform: "plataforma", year: "ano", ordering: "ordem" };
  const setFilter = (key, value) => update({ [urlKeys[key]]: value });

  const genres = useAsync((signal) => gamesApi.genres({ signal }), []);
  const platforms = useAsync((signal) => gamesApi.platforms({ signal }), []);
  const catalog = useAsync(
    (signal) =>
      gamesApi.catalog(
        { q: q || undefined, genre: genre || undefined, platform: platform || undefined, year: year || undefined, ordering: ordering || undefined, page, per_page: PER_PAGE },
        { signal },
      ),
    [q, genre, platform, year, ordering, page],
  );

  const filtered = Boolean(q || genre || platform || year || ordering);
  const data = catalog.data;
  const totalPages = data ? Math.min(MAX_PAGES, Math.max(1, Math.ceil(data.count / PER_PAGE))) : null;
  const shownOrdering = ordering || (q ? "relevance" : "popular");

  return (
    <div className="container page">
      <PageHeader
        title="Jogos"
        lead="Catálogo de jogos com dados da RAWG. Procure por nome ou filtre por gênero, plataforma e ano."
      />

      <form className="filters" role="search" aria-label="Filtros do catálogo" onSubmit={(event) => { event.preventDefault(); update({ q: text.trim() }); }}>
        <div className="filter filter-wide">
          <label htmlFor="catalog-q">Nome do jogo</label>
          <div className="input-icon">
            <Icon name="search" size={18} />
            <input id="catalog-q" type="search" value={text} maxLength={100} placeholder="Ex.: Hades" autoComplete="off" onChange={(event) => setText(event.target.value)} />
          </div>
        </div>
        <div className="filter">
          <label htmlFor="catalog-genre">Gênero</label>
          <select id="catalog-genre" value={genre} onChange={(event) => setFilter("genre", event.target.value)}>
            <option value="">Todos</option>
            {(genres.data?.items ?? []).map((item) => (
              <option key={item.slug} value={item.slug}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="catalog-platform">Plataforma</label>
          <select id="catalog-platform" value={platform} onChange={(event) => setFilter("platform", event.target.value)}>
            <option value="">Todas</option>
            {(platforms.data?.items ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter filter-narrow">
          <label htmlFor="catalog-year">Ano</label>
          <select id="catalog-year" value={year} onChange={(event) => setFilter("year", event.target.value)}>
            <option value="">Todos</option>
            {YEARS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <div className="filter filter-order">
          <label htmlFor="catalog-order">Ordenar por</label>
          <select id="catalog-order" value={shownOrdering} onChange={(event) => setFilter("ordering", event.target.value)}>
            {ORDERINGS.filter((item) => item.value !== "relevance" || q).map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        {filtered && (
          <button type="button" className="btn btn-quiet filter-clear" onClick={() => { setText(""); setParams({}); }}>
            Limpar filtros
          </button>
        )}
      </form>
      {(genres.error || platforms.error) && (
        <p className="form-note" role="status">
          Alguns filtros não carregaram agora; a busca por nome continua funcionando.
        </p>
      )}

      <div className="catalog-status" role="status" aria-live="polite">
        {data && !catalog.loading && (
          <p>{data.count === 0 ? "Nenhum jogo encontrado." : `${data.count.toLocaleString("pt-BR")} jogos`}</p>
        )}
      </div>

      {catalog.error && !data ? (
        <ErrorState error={catalog.error} onRetry={catalog.reload} />
      ) : !data ? (
        <GameGridSkeleton count={PER_PAGE} />
      ) : data.results.length === 0 ? (
        <EmptyState
          title="Nenhum jogo com esses filtros"
          action={
            filtered && (
              <button type="button" className="btn" onClick={() => { setText(""); setParams({}); }}>
                Limpar filtros
              </button>
            )
          }
        >
          Tente outro nome ou afrouxe os filtros.
        </EmptyState>
      ) : (
        <div aria-busy={catalog.loading || undefined} data-loading={catalog.loading || undefined}>
          <GameGrid>
            {data.results.map((game) => (
              <GameCard key={game.rawg_id} game={game} />
            ))}
          </GameGrid>
          <Pagination
            page={page}
            hasNext={data.has_next && page < MAX_PAGES}
            totalPages={totalPages}
            label="Páginas do catálogo"
            onPage={(next) => {
              update({ pagina: next > 1 ? String(next) : "" });
              window.scrollTo({ top: 0 });
            }}
          />
        </div>
      )}
    </div>
  );
}
