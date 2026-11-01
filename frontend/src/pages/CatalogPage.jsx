import { useEffect, useState } from "react";
import { GameGrid, GameGridSkeleton, Section } from "../components/Layout.jsx";
import { GameShelf, LibraryGameCard, ShelfItem, ShelfSkeleton } from "../components/GameShelf.jsx";
import { Pagination } from "../components/Pagination.jsx";
import { EmptyState, ErrorState } from "../components/States.jsx";
import { Icon } from "../components/Icon.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDebounced } from "../hooks/useDebounced.js";
import { useDiaryEntries } from "../hooks/useDiaryEntries.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link, useSearchParams } from "../router/index.jsx";
import { gamesApi } from "../services/api.js";

const PER_PAGE = 24;
const MAX_PAGES = 400; // a RAWG limita a paginação profunda
const SHELF_SIZE = 12;

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

/** Um filtro ativo (plataforma, ano ou ordem), com o "x" para tirá-lo. */
function ActiveFilter({ label, onRemove }) {
  return (
    <li>
      <button type="button" className="filter-chip" onClick={onRemove} aria-label={`Remover o filtro ${label}`}>
        {label}
        <Icon name="x" size={14} />
      </button>
    </li>
  );
}

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
  const [panelOpen, setPanelOpen] = useState(false);
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
  const clearAll = () => {
    setText("");
    setParams({});
  };

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
  // Sem busca nem filtro, a primeira página abre com prateleiras (em alta, lançamentos, melhores notas da comunidade).
  const discover = !filtered && page === 1;
  const featured = useAsync((signal) => (discover ? gamesApi.featured({ signal }) : Promise.resolve(null)), [discover]);
  const topRated = useAsync((signal) => (discover ? gamesApi.topRated({ per_page: SHELF_SIZE }, { signal }) : Promise.resolve(null)), [discover]);

  const data = catalog.data;
  const popular = discover ? (featured.data?.popular ?? []).slice(0, SHELF_SIZE) : [];
  const recent = discover ? (featured.data?.new ?? []).slice(0, SHELF_SIZE) : [];
  const best = discover ? (topRated.data?.items ?? []) : [];
  const diary = useDiaryEntries([
    ...(data?.results ?? []).map((game) => game.rawg_id),
    ...popular.map((game) => game.rawg_id),
    ...recent.map((game) => game.rawg_id),
    ...best.map((item) => item.game.rawg_id),
  ]);

  const totalPages = data ? Math.min(MAX_PAGES, Math.max(1, Math.ceil(data.count / PER_PAGE))) : null;
  const shownOrdering = ordering || (q ? "relevance" : "popular");
  const platformName = platforms.data?.items.find((item) => String(item.id) === platform)?.name ?? platform;
  const orderingLabel = ORDERINGS.find((item) => item.value === ordering)?.label ?? ordering;
  const panelFilters = [platform, year, ordering].filter(Boolean).length;
  const featuredLoading = discover && !featured.data && !featured.error;

  const results = data && data.results.length > 0 && (
    <div aria-busy={catalog.loading || undefined} data-loading={catalog.loading || undefined}>
      <GameGrid>
        {data.results.map((game) => (
          <LibraryGameCard key={game.rawg_id} game={game} diary={diary} />
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
  );

  return (
    <div className="container page catalog">
      <header className="catalog-head">
        <h1 className="catalog-title">Jogos</h1>
        <p className="catalog-count" role="status" aria-live="polite">
          {data && !catalog.loading ? (data.count === 0 ? "Nenhum jogo encontrado." : `${data.count.toLocaleString("pt-BR")} jogos`) : ""}
        </p>
      </header>

      <form
        className="catalog-bar"
        role="search"
        aria-label="Buscar jogos"
        onSubmit={(event) => {
          event.preventDefault();
          update({ q: text.trim() });
        }}
      >
        <div className="input-icon catalog-search">
          <Icon name="search" size={18} />
          <input
            id="catalog-q"
            type="search"
            aria-label="Nome do jogo"
            value={text}
            maxLength={100}
            placeholder="Procurar um jogo"
            autoComplete="off"
            onChange={(event) => setText(event.target.value)}
          />
        </div>
        <button
          type="button"
          className="btn catalog-filter-toggle"
          aria-expanded={panelOpen}
          aria-controls="catalog-filters"
          onClick={() => setPanelOpen((open) => !open)}
        >
          Filtros
          {panelFilters > 0 && (
            <span className="count-badge">
              {panelFilters}
              <span className="sr-only"> {panelFilters === 1 ? "filtro ativo" : "filtros ativos"}</span>
            </span>
          )}
        </button>
      </form>

      <div id="catalog-filters" className="catalog-panel" hidden={!panelOpen}>
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
        <div className="filter">
          <label htmlFor="catalog-year">Ano de lançamento</label>
          <select id="catalog-year" value={year} onChange={(event) => setFilter("year", event.target.value)}>
            <option value="">Todos</option>
            {YEARS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="catalog-order">Ordenar por</label>
          <select id="catalog-order" value={shownOrdering} onChange={(event) => setFilter("ordering", event.target.value)}>
            {ORDERINGS.filter((item) => item.value !== "relevance" || q).map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {(genres.data?.items ?? []).length > 0 && (
        <div className="genre-chips" role="group" aria-label="Gênero">
          <button type="button" className="genre-chip" aria-pressed={!genre} onClick={() => setFilter("genre", "")}>
            Todos
          </button>
          {genres.data.items.map((item) => (
            <button
              key={item.slug}
              type="button"
              className="genre-chip"
              aria-pressed={genre === item.slug}
              onClick={() => setFilter("genre", genre === item.slug ? "" : item.slug)}
            >
              {item.name}
            </button>
          ))}
        </div>
      )}

      {filtered && (
        <ul className="filter-chips" aria-label="Filtros ativos">
          {platform && <ActiveFilter label={`Plataforma: ${platformName}`} onRemove={() => setFilter("platform", "")} />}
          {year && <ActiveFilter label={`Ano: ${year}`} onRemove={() => setFilter("year", "")} />}
          {ordering && <ActiveFilter label={`Ordem: ${orderingLabel}`} onRemove={() => setFilter("ordering", "")} />}
          <li>
            <button type="button" className="btn btn-quiet filter-clear" onClick={clearAll}>
              Limpar tudo
            </button>
          </li>
        </ul>
      )}
      {(genres.error || platforms.error) && (
        <p className="form-note" role="status">
          Alguns filtros não carregaram agora; a busca por nome continua funcionando.
        </p>
      )}

      {discover && (
        <div className="catalog-shelves">
          {featuredLoading && <ShelfSkeleton title="Em alta" />}
          {popular.length > 0 && (
            <GameShelf
              title="Em alta"
              action={
                <Link to="/jogos?ordem=popular" className="section-link">
                  Ver todos
                </Link>
              }
            >
              {popular.map((game) => (
                <ShelfItem key={game.rawg_id}>
                  <LibraryGameCard game={game} diary={diary} />
                </ShelfItem>
              ))}
            </GameShelf>
          )}
          {recent.length > 0 && (
            <GameShelf
              title="Lançamentos recentes"
              action={
                <Link to="/jogos?ordem=released" className="section-link">
                  Ver todos
                </Link>
              }
            >
              {recent.map((game) => (
                <ShelfItem key={game.rawg_id}>
                  <LibraryGameCard game={game} diary={diary} />
                </ShelfItem>
              ))}
            </GameShelf>
          )}
          {best.length > 0 && (
            <GameShelf title="Mais bem avaliados no DiscPlayer">
              {best.map((item) => (
                <ShelfItem key={item.game.rawg_id}>
                  <LibraryGameCard game={item.game} diary={diary} community={{ average: item.average, count: item.count }} showGenre={false} />
                </ShelfItem>
              ))}
            </GameShelf>
          )}
        </div>
      )}

      {catalog.error && !data ? (
        <ErrorState error={catalog.error} onRetry={catalog.reload} />
      ) : !data ? (
        <GameGridSkeleton count={PER_PAGE} />
      ) : data.results.length === 0 ? (
        <EmptyState
          title="Nenhum jogo com esses filtros"
          action={
            filtered && (
              <button type="button" className="btn" onClick={clearAll}>
                Limpar filtros
              </button>
            )
          }
        >
          Tente outro nome ou afrouxe os filtros.
        </EmptyState>
      ) : discover ? (
        <Section title="Todos os jogos" className="catalog-all">
          {results}
        </Section>
      ) : (
        <section aria-label="Resultados" className="catalog-results">
          {results}
        </section>
      )}
    </div>
  );
}
