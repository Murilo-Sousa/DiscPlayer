import { useEffect, useState } from "react";
import { Dialog } from "../../components/Dialog.jsx";
import { Field } from "../../components/Field.jsx";
import { Icon } from "../../components/Icon.jsx";
import { StatusPicker } from "../../components/StatusPicker.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { useToast } from "../../context/ToastContext.jsx";
import { Link, useLocation } from "../../router/index.jsx";
import { libraryApi } from "../../services/api.js";
import { canReplay, hasCompletionDate, hasStarted, isReleased, statusBlockedReason } from "../../utils/diary.js";
import { STATUS_LABELS, daysBetween, formatDate, playSpan, plural } from "../../utils/format.js";
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
 *
 * O que aparece depende do status (regras em utils/diary.js): "Quero jogar" é um jogo que ainda não começou, então não
 * tem datas nem favorito; só um jogo zerado tem data de término; e um jogo que ainda não saiu só vai para a fila.
 */
export function DiaryPanel({ rawgId, game, entry, hasRating = false, playthroughs = [], onSaved, onReplayed, onPlaythroughsChanged, onRemoved, onOutdated }) {
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
      // Erro de um campo que não está na tela (ou sem campo): o aviso vai para o toast, para não passar em branco.
      const shown = [
        "status",
        ...(entry && hasStarted(entry.status) ? ["started_at"] : []),
        ...(entry && hasCompletionDate(entry.status) ? ["completed_at"] : []),
      ];
      if (!error.fields || Object.keys(error.fields).some((name) => !shown.includes(name))) toast.error(error.message);
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
      const result = await libraryApi.remove(rawgId, { withReview: hasRating });
      setConfirmRemove(false);
      onRemoved(result);
      toast.success(result?.review_removed ? "Jogo e nota removidos do seu diário." : "Jogo removido do seu diário.");
    } catch (error) {
      setConfirmRemove(false);
      if (error.code === "review_would_be_removed") {
        // A tela estava desatualizada (a nota foi dada em outra aba): nada foi apagado. Recarrega para o aviso certo.
        toast.error("Este jogo tem uma nota sua que esta tela ainda não mostrava, então nada foi removido. Confira e tente de novo.");
        onOutdated?.();
      } else {
        toast.error(error.message);
      }
    } finally {
      setPending(false);
    }
  };

  const started = entry ? hasStarted(entry.status) : false;
  const completable = entry ? hasCompletionDate(entry.status) : false;
  const datesChanged =
    entry &&
    (dates.started_at !== (entry.started_at ?? "") || (completable && dates.completed_at !== (entry.completed_at ?? "")));
  const span = completable && entry?.started_at && entry?.completed_at ? daysBetween(entry.started_at, entry.completed_at) : null;

  // Status que não dá para escolher agora, com o motivo por escrito (e não só um botão apagado).
  const blocked = {};
  for (const status of Object.keys(STATUS_LABELS)) {
    const reason = statusBlockedReason(status, { game, hasRating, playthroughs: playthroughs.length });
    if (reason && status !== entry?.status) blocked[status] = reason;
  }
  const unreleased = !isReleased(game?.released);
  // Jogo que ainda não saiu já é explicado logo acima do seletor; os outros motivos aparecem abaixo dele.
  const reasons = unreleased ? [] : [...new Set(Object.values(blocked))];

  return (
    <section className="panel" aria-labelledby="diary-title">
      <div className="panel-head">
        <h2 id="diary-title" className="panel-title">
          Seu diário
        </h2>
        {entry && started && (
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

      <p id="diary-hint" className="panel-hint">
        {unreleased
          ? `Lança em ${formatDate(game.released)}. Até lá, só dá para guardá-lo em “Quero jogar”.`
          : entry
            ? "Mude o status quando o seu jogo avançar."
            : "Como esse jogo está para você?"}
      </p>
      <StatusPicker
        value={entry?.status ?? null}
        disabled={pending}
        blocked={blocked}
        describedBy={reasons.length ? "status-blocked" : unreleased ? "diary-hint" : undefined}
        onChange={(status) => status !== entry?.status && save({ status }, `${STATUS_LABELS[status]}: salvo no seu diário.`)}
      />
      {reasons.length > 0 && (
        <p id="status-blocked" className="field-hint status-blocked">
          {reasons.join(" ")}
        </p>
      )}
      {errors.status && <p className="field-error">{errors.status}</p>}

      {entry && canReplay(entry.status) && (
        <div className="replay-row">
          <button type="button" className="btn" disabled={pending} onClick={() => setConfirmReplay(true)}>
            Jogar de novo
          </button>
          <p className="field-hint">Guarda esta jogada no histórico e começa outra, hoje.</p>
        </div>
      )}

      {entry && (
        <>
          {started ? (
            <form
              className="date-form"
              data-fields={completable ? "2" : "1"}
              onSubmit={(event) => {
                event.preventDefault();
                save(
                  completable
                    ? { started_at: dates.started_at || null, completed_at: dates.completed_at || null }
                    : { started_at: dates.started_at || null },
                  "Datas salvas.",
                );
              }}
            >
              <Field
                label="Comecei em"
                type="date"
                value={dates.started_at}
                max={(completable && dates.completed_at) || undefined}
                onChange={(event) => setDates((current) => ({ ...current, started_at: event.target.value }))}
                error={errors.started_at}
              />
              {completable && (
                <Field
                  label="Terminei em"
                  type="date"
                  value={dates.completed_at}
                  min={dates.started_at || undefined}
                  onChange={(event) => setDates((current) => ({ ...current, completed_at: event.target.value }))}
                  error={errors.completed_at}
                />
              )}
              <button type="submit" className="btn" disabled={pending || !datesChanged}>
                Salvar datas
              </button>
            </form>
          ) : (
            <p className="panel-hint queue-hint">
              Na fila. Quando você começar, mude o status para “Jogando”: a data de início, o favorito e a nota ficam
              disponíveis.
            </p>
          )}
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
          O jogo sai do seu diário, junto com as datas, o favorito e o histórico de jogadas.
          {hasRating &&
            " A sua nota e a sua review também saem do DiscPlayer (e da média do jogo), porque só dá para avaliar um jogo que está no seu diário."}
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
