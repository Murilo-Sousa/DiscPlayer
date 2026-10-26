import { useEffect, useState } from "react";
import { Dialog } from "../../components/Dialog.jsx";
import { Icon } from "../../components/Icon.jsx";
import { ErrorState, Loader } from "../../components/States.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { useToast } from "../../context/ToastContext.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { Link } from "../../router/index.jsx";
import { listsApi } from "../../services/api.js";
import { listPath, plural } from "../../utils/format.js";
import { LoginPrompt } from "./DiaryPanel.jsx";

/** Botão e janela para guardar o jogo em listas (e criar uma lista nova na hora). */
export function ListsPanel({ rawgId, memberIds, onChange }) {
  const { user } = useAuth();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(null);
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [titleError, setTitleError] = useState("");
  const state = useAsync((signal) => (open && user ? listsApi.mine({ signal }) : Promise.resolve(null)), [open, user?.username]);

  useEffect(() => {
    if (!open) {
      setTitle("");
      setTitleError("");
    }
  }, [open]);

  if (!user) {
    return (
      <section className="panel" aria-labelledby="lists-title">
        <h2 id="lists-title" className="panel-title">
          Listas
        </h2>
        <LoginPrompt>Entre para guardar este jogo em listas suas.</LoginPrompt>
      </section>
    );
  }

  const toggle = async (list) => {
    const isIn = memberIds.includes(list.id);
    setBusy(list.id);
    try {
      if (isIn) await listsApi.removeGame(list.id, rawgId);
      else await listsApi.addGame(list.id, rawgId);
      onChange(isIn ? memberIds.filter((id) => id !== list.id) : [...memberIds, list.id]);
      state.reload();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setBusy(null);
    }
  };

  const create = async (event) => {
    event.preventDefault();
    const name = title.trim();
    if (!name) {
      setTitleError("Dê um nome para a lista.");
      return;
    }
    setCreating(true);
    setTitleError("");
    try {
      const { list } = await listsApi.create({ title: name, is_public: true });
      await listsApi.addGame(list.id, rawgId);
      onChange([...memberIds, list.id]);
      setTitle("");
      state.reload();
      toast.success(`Lista “${list.title}” criada com este jogo.`);
    } catch (error) {
      setTitleError(error.fields?.title ?? error.message);
    } finally {
      setCreating(false);
    }
  };

  const lists = state.data?.items ?? [];

  return (
    <section className="panel panel-row" aria-labelledby="lists-title">
      <div className="panel-row-text">
        <h2 id="lists-title" className="panel-title">
          Listas
        </h2>
        <p className="panel-hint">
          {memberIds.length === 0 ? "Este jogo ainda não está em nenhuma lista sua." : `Está em ${plural(memberIds.length, "lista sua", "listas suas")}.`}
        </p>
      </div>
      <button type="button" className="btn" onClick={() => setOpen(true)}>
        <Icon name="plus" size={18} />
        Guardar em lista
      </button>

      <Dialog open={open} onClose={() => setOpen(false)} title="Guardar em lista">
        {state.error && !state.data ? (
          <ErrorState error={state.error} onRetry={state.reload} compact />
        ) : !state.data ? (
          <Loader label="Carregando suas listas" />
        ) : (
          <>
            {lists.length === 0 ? (
              <p className="muted">Você ainda não tem listas. Crie a primeira abaixo.</p>
            ) : (
              <ul className="check-list">
                {lists.map((list) => {
                  const checked = memberIds.includes(list.id);
                  return (
                    <li key={list.id} className="check-row">
                      <label className="check-label">
                        <input type="checkbox" checked={checked} disabled={busy === list.id} onChange={() => toggle(list)} />
                        <span className="check-text">
                          <span>{list.title}</span>
                          <span className="muted">
                            {plural(list.game_count, "jogo", "jogos")}
                            {!list.is_public && ", privada"}
                          </span>
                        </span>
                      </label>
                      <Link to={listPath(list.id)} className="check-open" onClick={() => setOpen(false)}>
                        Abrir
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
            <form className="inline-form" onSubmit={create} noValidate>
              <div className="field" data-invalid={titleError ? "true" : undefined}>
                <label className="field-label" htmlFor="new-list-title">
                  Nova lista com este jogo
                </label>
                <input id="new-list-title" value={title} maxLength={80} onChange={(event) => setTitle(event.target.value)} aria-invalid={!!titleError} aria-describedby={titleError ? "new-list-error" : undefined} placeholder="Ex.: Para jogar no inverno" />
                {titleError && (
                  <p className="field-error" id="new-list-error">
                    {titleError}
                  </p>
                )}
              </div>
              <button type="submit" className="btn btn-primary" disabled={creating}>
                Criar lista
              </button>
            </form>
          </>
        )}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={() => setOpen(false)}>
            Concluir
          </button>
        </div>
      </Dialog>
    </section>
  );
}
