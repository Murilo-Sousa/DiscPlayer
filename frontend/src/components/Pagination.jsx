import { Icon } from "./Icon.jsx";

/** Anterior/próxima com a posição atual. `totalPages` é opcional (a RAWG informa o total; as listas locais, não). */
export function Pagination({ page, hasNext, totalPages, onPage, label = "Paginação" }) {
  if (page <= 1 && !hasNext) return null;
  return (
    <nav className="pagination" aria-label={label}>
      <button type="button" className="btn" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <Icon name="left" size={18} />
        Anterior
      </button>
      <span className="pagination-position">{totalPages ? `Página ${page} de ${totalPages}` : `Página ${page}`}</span>
      <button type="button" className="btn" disabled={!hasNext} onClick={() => onPage(page + 1)}>
        Próxima
        <Icon name="right" size={18} />
      </button>
    </nav>
  );
}
