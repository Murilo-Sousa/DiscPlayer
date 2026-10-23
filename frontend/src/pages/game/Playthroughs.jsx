import { useState } from "react";
import { Dialog } from "../../components/Dialog.jsx";
import { StatusBadge } from "../../components/StatusPicker.jsx";
import { useToast } from "../../context/ToastContext.jsx";
import { libraryApi } from "../../services/api.js";
import { playSpan } from "../../utils/format.js";

/**
 * Histórico de jogadas de um jogo: as anteriores (que dá para excluir) e a atual.
 * Só aparece depois do primeiro "Jogar de novo".
 */
export function Playthroughs({ rawgId, entry, playthroughs, onChanged }) {
  const toast = useToast();
  const [target, setTarget] = useState(null); // { id, number }
  const [pending, setPending] = useState(false);

  if (!entry || playthroughs.length === 0) return null;

  const remove = async () => {
    setPending(true);
    try {
      const result = await libraryApi.removePlaythrough(rawgId, target.id);
      setTarget(null);
      onChanged(result);
      toast.success("Jogada excluída do histórico.");
    } catch (error) {
      toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="playthroughs" aria-labelledby="plays-title">
      <h3 id="plays-title" className="playthroughs-title">
        Suas jogadas
      </h3>
      <ol className="playthrough-list">
        {playthroughs.map((play, index) => (
          <li key={play.id} className="playthrough">
            <span className="playthrough-number">Jogada {index + 1}</span>
            <StatusBadge status={play.status} />
            <span className="playthrough-dates">{playSpan(play)}</span>
            <button
              type="button"
              className="link-btn link-danger playthrough-remove"
              onClick={() => setTarget({ id: play.id, number: index + 1 })}
            >
              Excluir<span className="sr-only"> a jogada {index + 1}</span>
            </button>
          </li>
        ))}
        <li className="playthrough" data-current="true">
          <span className="playthrough-number">Jogada {playthroughs.length + 1}</span>
          <StatusBadge status={entry.status} />
          <span className="playthrough-dates">{playSpan(entry)}</span>
          <span className="playthrough-now">atual</span>
        </li>
      </ol>

      <Dialog open={target !== null} onClose={() => !pending && setTarget(null)} title={`Excluir a jogada ${target?.number ?? ""}?`}>
        <p>
          Ela sai do histórico deste jogo e deixa de contar nas suas estatísticas, como as zeradas do ano. A sua nota, a sua
          review e a jogada atual não mudam.
        </p>
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={() => setTarget(null)} disabled={pending}>
            Cancelar
          </button>
          <button type="button" className="btn btn-danger" onClick={remove} disabled={pending}>
            Excluir jogada
          </button>
        </div>
      </Dialog>
    </section>
  );
}
