import { useEffect, useState } from "react";
import { Dialog } from "../../components/Dialog.jsx";
import { Field } from "../../components/Field.jsx";
import { Icon } from "../../components/Icon.jsx";
import { StatusPicker } from "../../components/StatusPicker.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { useToast } from "../../context/ToastContext.jsx";
import { Link, useLocation } from "../../router/index.jsx";
import { libraryApi } from "../../services/api.js";
import { REPLAYABLE, STATUS_LABELS, daysBetween, formatDate, playSpan, plural } from "../../utils/format.js";
import { Playthroughs } from "./Playthroughs.jsx";

export function LoginPrompt({ children }) {
  const { pathname, search } = useLocation();
  const next = encodeURIComponent(pathname + search);
  return (
    <div className="panel-prompt">
      <p>{children}</p>
      <div className="panel-prompt-actions">
        <Link to={`/entrar?proximo=${next}`} className="btn btn-primary">
          Entrar
        </Link>
        <Link to={`/cadastro?proximo=${next}`} className="btn">
          Criar conta
        </Link>
      </div>
    </div>
  );
}

/**
 * Registro do jogo no diário de quem está logado: status, favorito, datas, "jogar de novo" (com o
 * histórico das jogadas anteriores) e remoção.
 */
export function DiaryPanel({ rawgId, entry, playthroughs = [], onSaved, onReplayed, onPlaythroughsChanged, onRemoved }) {
  const { user } = useAuth();
  const toast = useToast();
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState({});
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [confirmReplay, setConfirmReplay] = useState(false);
  const [dates, setDates] = useState({ started_at: entry?.started_at ?? "", completed_at: entry?.completed_at ?? "" });

  useEffect(() => {
    setDates({ started_at: entry?.started_at ?? "", completed_at: entry?.completed_at ?? "" });
  }, [entry?.started_at, entry?.completed_at]);

  if (!user) {
    return (
      <section className="panel" aria-labelledby="diary-title">
        <h2 id="diary-title" className="panel-title">
          Seu diário
        </h2>
        <LoginPrompt>Entre na sua conta para registrar este jogo, dar uma nota e guardar em listas.</LoginPrompt>
      </section>
    );
  }

  const save = async (changes, message) => {
    setPending(true);
    setErrors({});
    try {
      const result = await libraryApi.save(rawgId, changes);
      onSaved(result.entry, result.rating);
      if (message) toast.success(message);
    } catch (error) {
      setErrors(error.fields ?? {});
      if (!error.fields) toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  const replay = async () => {
    setPending(true);
    try {
      const result = await libraryApi.replay(rawgId);
      setConfirmReplay(false);
      onReplayed(result);
      toast.success("Nova jogada começada. A anterior ficou no histórico.");
    } catch (error) {
      setConfirmReplay(false);
      toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  const remove = async () => {
    setPending(true);
    try {
      await libraryApi.remove(rawgId);
      setConfirmRemove(false);
      onRemoved();
      toast.success("Jogo removido do seu diário.");
    } catch (error) {
      toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  const datesChanged =
    entry && (dates.started_at !== (entry.started_at ?? "") || dates.completed_at !== (entry.completed_at ?? ""));
  const span = entry?.started_at && entry?.completed_at ? daysBetween(entry.started_at, entry.completed_at) : null;

  return (
    <section className="panel" aria-labelledby="diary-title">
      <div className="panel-head">
        <h2 id="diary-title" className="panel-title">
          Seu diário
        </h2>
        {entry && (
          <button
            type="button"
            className="like-btn"
            aria-pressed={entry.is_favorite}
            disabled={pending}
            onClick={() =>
              save({ is_favorite: !entry.is_favorite }, entry.is_favorite ? "Removido dos favoritos." : "Marcado como favorito.")
            }
          >
            <Icon name="heart" size={16} filled={entry.is_favorite} />
            <span>{entry.is_favorite ? "Favorito" : "Favoritar"}</span>
          </button>
        )}
      </div>

      <p className="panel-hint">{entry ? "Mude o status quando o seu jogo avançar." : "Como esse jogo está para você?"}</p>
      <StatusPicker
        value={entry?.status ?? null}
        disabled={pending}
        onChange={(status) => status !== entry?.status && save({ status }, `${STATUS_LABELS[status]}: salvo no seu diário.`)}
      />
      {errors.status && <p className="field-error">{errors.status}</p>}

      {entry && REPLAYABLE.includes(entry.status) && (
        <div className="replay-row">
          <button type="button" className="btn" disabled={pending} onClick={() => setConfirmReplay(true)}>
            Jogar de novo
          </button>
          <p className="field-hint">Guarda esta jogada no histórico e começa outra, hoje.</p>
        </div>
      )}

      {entry && (
        <>
          <form
            className="date-form"
            onSubmit={(event) => {
              event.preventDefault();
              save({ started_at: dates.started_at || null, completed_at: dates.completed_at || null }, "Datas salvas.");
            }}
          >
            <Field
              label="Comecei em"
              type="date"
              value={dates.started_at}
              max={dates.completed_at || undefined}
              onChange={(event) => setDates((current) => ({ ...current, started_at: event.target.value }))}
              error={errors.started_at}
            />
            <Field
              label="Terminei em"
              type="date"
              value={dates.completed_at}
              min={dates.started_at || undefined}
              onChange={(event) => setDates((current) => ({ ...current, completed_at: event.target.value }))}
              error={errors.completed_at}
            />
            <button type="submit" className="btn" disabled={pending || !datesChanged}>
              Salvar datas
            </button>
          </form>
          {span !== null && span >= 0 && (
            <p className="panel-hint">
              {span === 0 ? "Começou e terminou no mesmo dia." : `${plural(span, "dia", "dias")} entre começar e terminar.`}
            </p>
          )}
          <Playthroughs rawgId={rawgId} entry={entry} playthroughs={playthroughs} onChanged={onPlaythroughsChanged} />
          <p className="panel-foot">
            Registrado em {formatDate(entry.created_at)}.{" "}
            <button type="button" className="link-btn link-danger" onClick={() => setConfirmRemove(true)}>
              Remover do diário
            </button>
          </p>
        </>
      )}

      <Dialog open={confirmReplay} onClose={() => !pending && setConfirmReplay(false)} title="Jogar de novo?">
        {entry && (
          <>
            <p>
              A jogada atual ({STATUS_LABELS[entry.status]}, {playSpan(entry).toLowerCase()}) fica guardada no histórico deste
              jogo, e você começa uma nova hoje.
            </p>
            <p className="dialog-note">A sua nota, a sua review e o favorito continuam como estão.</p>
          </>
        )}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={() => setConfirmReplay(false)} disabled={pending}>
            Cancelar
          </button>
          <button type="button" className="btn btn-primary" onClick={replay} disabled={pending}>
            Jogar de novo
          </button>
        </div>
      </Dialog>

      <Dialog open={confirmRemove} onClose={() => !pending && setConfirmRemove(false)} title="Remover do diário?">
        <p>
          O jogo sai do seu diário, junto com as datas, o favorito e o histórico de jogadas. A sua nota e a sua review, se
          existirem, continuam publicadas.
        </p>
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={() => setConfirmRemove(false)} disabled={pending}>
            Cancelar
          </button>
          <button type="button" className="btn btn-danger" onClick={remove} disabled={pending}>
            Remover
          </button>
        </div>
      </Dialog>
    </section>
  );
}
