import { useEffect, useRef, useState } from "react";
import { Cover, CoverStack } from "../components/Cover.jsx";
import { Dialog } from "../components/Dialog.jsx";
import { Icon } from "../components/Icon.jsx";
import { ListFormDialog } from "../components/ListFormDialog.jsx";
import { EmptyState, ErrorState, Loader } from "../components/States.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDebounced } from "../hooks/useDebounced.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link, useNavigate, useParams } from "../router/index.jsx";
import { gamesApi, listsApi } from "../services/api.js";
import { formatDate, formatYear, gamePath, paragraphs, plural, userPath } from "../utils/format.js";
import NotFoundPage from "./NotFoundPage.jsx";
import { DemoBadge } from "../components/DemoBadge.jsx";

function AddGamesDialog({ open, onClose, list, onAdded }) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(null);
  const term = useDebounced(text.trim(), 350);
  const enabled = open && term.length >= 2;
  const state = useAsync((signal) => (enabled ? gamesApi.catalog({ q: term, per_page: 10 }, { signal }) : Promise.resolve(null)), [enabled, term]);
  const inList = new Set(list.items.map((item) => item.game.rawg_id));

  useEffect(() => {
    if (!open) setText("");
  }, [open]);

  const add = async (game) => {
    setBusy(game.rawg_id);
    try {
      const result = await listsApi.addGame(list.id, game.rawg_id);
      onAdded(result.list);
      toast.success(`“${game.name}” entrou na lista.`);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title="Adicionar jogos" wide>
      <div className="field">
        <label className="field-label" htmlFor="add-game-q">
          Buscar jogo pelo nome
        </label>
        <div className="input-icon">
          <Icon name="search" size={18} />
          <input id="add-game-q" type="search" autoComplete="off" value={text} maxLength={100} onChange={(event) => setText(event.target.value)} autoFocus />
        </div>
      </div>
      <div className="add-results" aria-live="polite">
        {term.length < 2 ? (
          <p className="muted">Digite pelo menos 2 letras.</p>
        ) : state.error && !state.data ? (
          <ErrorState error={state.error} onRetry={state.reload} compact />
        ) : !state.data ? (
          <Loader label="Buscando jogos" />
        ) : state.data.results.length === 0 ? (
          <p className="muted">Nenhum jogo encontrado para “{term}”.</p>
        ) : (
          <ul className="add-list">
            {state.data.results.map((game) => {
              const already = inList.has(game.rawg_id);
              return (
                <li key={game.rawg_id} className="add-row">
                  <Cover game={game} ratio="poster" className="add-cover" />
                  <span className="add-text">
                    <span className="add-name">{game.name}</span>
                    <span className="muted">{formatYear(game.released)}</span>
                  </span>
                  <button type="button" className="btn" disabled={already || busy === game.rawg_id || list.items.length >= 200} onClick={() => add(game)}>
                    {already ? "Na lista" : "Adicionar"}
                    <span className="sr-only">: {game.name}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="dialog-actions">
        <button type="button" className="btn btn-primary" onClick={onClose}>
          Concluir
        </button>
      </div>
    </Dialog>
  );
}

export default function ListPage() {
  const { id } = useParams();
  const listId = /^\d+$/.test(id) ? Number(id) : null;
  const navigate = useNavigate();
  const toast = useToast();
  const state = useAsync(
    (signal) => (listId === null ? Promise.reject(Object.assign(new Error("Lista não encontrada."), { status: 404 })) : listsApi.get(listId, { signal })),
    [listId],
  );
  const list = state.data?.list ?? null;
  useDocumentTitle(list?.title ?? "Lista");

  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const focusAfter = useRef(null);

  useEffect(() => {
    const target = focusAfter.current;
    if (!target) return;
    focusAfter.current = null;
    const wanted = document.getElementById(`move-${target.dir}-${target.id}`);
    const other = document.getElementById(`move-${target.dir === "up" ? "down" : "up"}-${target.id}`);
    (wanted && !wanted.disabled ? wanted : other)?.focus();
  }, [list]);

  if (state.error && !list) {
    if (state.error.status === 404) {
      return <NotFoundPage title="Lista não encontrada">Ela pode ter sido removida ou ser privada.</NotFoundPage>;
    }
    return (
      <div className="container page">
        <ErrorState error={state.error} onRetry={state.reload} />
      </div>
    );
  }
  if (!list) {
    return (
      <div className="container page page-loading">
        <Loader label="Carregando a lista" />
      </div>
    );
  }

  const setList = (next) => state.setData(() => ({ list: next }));
  const description = paragraphs(list.description);

  const move = async (index, delta) => {
    const items = [...list.items];
    const target = index + delta;
    if (target < 0 || target >= items.length) return;
    const moved = items[index];
    [items[index], items[target]] = [items[target], items[index]];
    focusAfter.current = { id: moved.game.rawg_id, dir: delta < 0 ? "up" : "down" };
    setList({ ...list, items: items.map((item, position) => ({ ...item, position })) });
    try {
      const result = await listsApi.reorder(list.id, items.map((item) => item.game.rawg_id));
      setList(result.list);
    } catch (error) {
      toast.error(error.message);
      state.reload();
    }
  };

  const removeGame = async (item) => {
    setBusy(true);
    try {
      const result = await listsApi.removeGame(list.id, item.game.rawg_id);
      setList(result.list);
      toast.success(`“${item.game.name}” saiu da lista.`);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(false);
    }
  };

  const deleteList = async () => {
    setBusy(true);
    try {
      await listsApi.remove(list.id);
      toast.success("Lista excluída.");
      navigate("/listas?aba=minhas", { replace: true });
    } catch (error) {
      toast.error(error.message);
      setBusy(false);
    }
  };

  return (
    <div className="container page list-page">
      <header className="list-head">
        <CoverStack covers={list.covers} className="list-head-covers" />
        <div className="list-head-text">
          <p className="eyebrow">
            Lista de <Link to={userPath(list.owner.username)}>{list.owner.display_name}</Link>
            <DemoBadge user={list.owner} />
            {!list.is_public && (
              <span className="badge">
                <Icon name="lock" size={13} /> Privada
              </span>
            )}
          </p>
          <h1 className="page-title">{list.title}</h1>
          {description.length > 0 && (
            <div className="prose list-description">
              {description.map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </div>
          )}
          <p className="muted">{plural(list.items.length, "jogo", "jogos")}</p>
          {list.is_owner && (
            <div className="list-owner-actions">
              <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
                <Icon name="plus" size={18} />
                Adicionar jogos
              </button>
              <button type="button" className="btn" onClick={() => setEditing(true)}>
                <Icon name="edit" size={18} />
                Editar
              </button>
              <button type="button" className="btn btn-quiet link-danger" onClick={() => setConfirmDelete(true)}>
                <Icon name="trash" size={18} />
                Excluir
              </button>
            </div>
          )}
        </div>
      </header>

      {list.items.length === 0 ? (
        <EmptyState
          title="Lista vazia"
          action={
            list.is_owner && (
              <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
                Adicionar o primeiro jogo
              </button>
            )
          }
        >
          {list.is_owner ? "Procure jogos pelo nome e monte a lista na ordem que quiser." : "Ainda não há jogos nesta lista."}
        </EmptyState>
      ) : (
        <ol className="list-items" aria-busy={state.loading || undefined}>
          {list.items.map((item, index) => (
            <li key={item.game.rawg_id} className="list-item">
              <span className="list-item-position" aria-hidden="true">
                {index + 1}
              </span>
              <Link to={gamePath(item.game)} className="list-item-cover" tabIndex={-1} aria-hidden="true">
                <Cover game={item.game} ratio="poster" />
              </Link>
              <span className="list-item-text">
                <Link to={gamePath(item.game)} className="list-item-name">
                  {item.game.name}
                </Link>
                <span className="muted">
                  {[formatYear(item.game.released), `adicionado em ${formatDate(item.added_at)}`].filter(Boolean).join(", ")}
                </span>
              </span>
              {list.is_owner && (
                <span className="list-item-tools">
                  <button type="button" id={`move-up-${item.game.rawg_id}`} className="icon-btn" disabled={index === 0} onClick={() => move(index, -1)} aria-label={`Mover ${item.game.name} para cima`}>
                    <Icon name="up" size={18} />
                  </button>
                  <button type="button" id={`move-down-${item.game.rawg_id}`} className="icon-btn" disabled={index === list.items.length - 1} onClick={() => move(index, 1)} aria-label={`Mover ${item.game.name} para baixo`}>
                    <Icon name="down" size={18} />
                  </button>
                  <button type="button" className="icon-btn" disabled={busy} onClick={() => removeGame(item)} aria-label={`Remover ${item.game.name} da lista`}>
                    <Icon name="x" size={18} />
                  </button>
                </span>
              )}
            </li>
          ))}
        </ol>
      )}

      {list.is_owner && (
        <>
          <ListFormDialog
            open={editing}
            list={list}
            onClose={() => setEditing(false)}
            onSaved={(next) => {
              setEditing(false);
              setList(next);
            }}
          />
          <AddGamesDialog open={adding} onClose={() => setAdding(false)} list={list} onAdded={setList} />
          <Dialog open={confirmDelete} onClose={() => !busy && setConfirmDelete(false)} title="Excluir esta lista?">
            <p>
              A lista “{list.title}” será apagada para sempre. Os jogos continuam no seu diário e no catálogo.
            </p>
            <div className="dialog-actions">
              <button type="button" className="btn" onClick={() => setConfirmDelete(false)} disabled={busy}>
                Cancelar
              </button>
              <button type="button" className="btn btn-danger" onClick={deleteList} disabled={busy}>
                Excluir lista
              </button>
            </div>
          </Dialog>
        </>
      )}
    </div>
  );
}
