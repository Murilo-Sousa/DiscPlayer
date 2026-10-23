import { useState } from "react";
import { Dialog } from "../../components/Dialog.jsx";
import { Field } from "../../components/Field.jsx";
import { RatingInput } from "../../components/RatingInput.jsx";
import { ReviewCard } from "../../components/ReviewCard.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { useToast } from "../../context/ToastContext.jsx";
import { reviewsApi } from "../../services/api.js";
import { LoginPrompt } from "./DiaryPanel.jsx";

export const REVIEW_MAX = 5000;

/** Nota (0–10, de 0,5 em 0,5) e texto opcional. Cada pessoa tem uma review por jogo. */
export function ReviewPanel({ rawgId, review, onChanged }) {
  const { user } = useAuth();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState(review?.rating ?? null);
  const [body, setBody] = useState(review?.body ?? "");
  const [spoilers, setSpoilers] = useState(review?.has_spoilers ?? false);
  const [errors, setErrors] = useState({});
  const [pending, setPending] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (!user) {
    return (
      <section className="panel" aria-labelledby="review-title">
        <h2 id="review-title" className="panel-title">
          Sua nota
        </h2>
        <LoginPrompt>Entre para dar uma nota de 0 a 10 e escrever o que achou.</LoginPrompt>
      </section>
    );
  }

  const startEditing = () => {
    setRating(review.rating);
    setBody(review.body ?? "");
    setSpoilers(review.has_spoilers ?? false);
    setErrors({});
    setEditing(true);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (rating === null) {
      setErrors({ rating: "Escolha uma nota de 0 a 10." });
      return;
    }
    if (body.length > REVIEW_MAX) {
      setErrors({ body: `A review pode ter até ${REVIEW_MAX} caracteres.` });
      return;
    }
    setPending(true);
    setErrors({});
    const text = body.trim();
    const payload = { rating, body: text || null, has_spoilers: Boolean(text) && spoilers };
    try {
      if (review) {
        await reviewsApi.update(review.id, payload);
        toast.success("Review atualizada.");
      } else {
        await reviewsApi.create(rawgId, payload);
        toast.success("Review publicada.");
      }
      setEditing(false);
      onChanged();
    } catch (error) {
      setErrors(error.fields ?? {});
      if (!error.fields) toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  const remove = async () => {
    setPending(true);
    try {
      await reviewsApi.remove(review.id);
      setConfirmDelete(false);
      setRating(null);
      setBody("");
      setSpoilers(false);
      toast.success("Review excluída.");
      onChanged();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  const showForm = !review || editing;

  return (
    <section className="panel" aria-labelledby="review-title">
      <h2 id="review-title" className="panel-title">
        {review ? "Sua review" : "Sua nota"}
      </h2>
      {showForm ? (
        <form className="form" onSubmit={submit} noValidate>
          <div className="field" data-invalid={errors.rating ? "true" : undefined}>
            <span className="field-label" id="rating-label">
              Nota
            </span>
            <RatingInput value={rating} onChange={setRating} disabled={pending} />
            {errors.rating && <p className="field-error">{errors.rating}</p>}
          </div>
          <Field
            label="O que você achou? (opcional)"
            as="textarea"
            rows={5}
            maxLength={REVIEW_MAX}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            error={errors.body}
            hint="Só texto. Quebras de linha viram parágrafos."
          />
          <div className="field">
            <label className="check-inline">
              <input
                type="checkbox"
                checked={spoilers && body.trim() !== ""}
                disabled={pending || body.trim() === ""}
                aria-describedby="spoiler-hint"
                onChange={(event) => setSpoilers(event.target.checked)}
              />
              <span>Esta review contém spoilers</span>
            </label>
            <p id="spoiler-hint" className="field-hint">
              O texto fica escondido atrás de um aviso, e o trecho não aparece no feed nem na busca.
            </p>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={pending}>
              {pending ? "Salvando…" : review ? "Salvar alterações" : "Publicar"}
            </button>
            {editing && (
              <button type="button" className="btn btn-quiet" onClick={() => setEditing(false)} disabled={pending}>
                Cancelar
              </button>
            )}
          </div>
        </form>
      ) : (
        <>
          <ReviewCard review={review} showAuthor={false} alwaysShow className="review-own" />
          <div className="form-actions">
            <button type="button" className="btn" onClick={startEditing}>
              Editar
            </button>
            <button type="button" className="btn btn-quiet link-danger" onClick={() => setConfirmDelete(true)}>
              Excluir
            </button>
          </div>
        </>
      )}
      <Dialog open={confirmDelete} onClose={() => !pending && setConfirmDelete(false)} title="Excluir sua review?">
        <p>A nota e o texto deixam de aparecer para a comunidade e saem da média do jogo. Isso não pode ser desfeito.</p>
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={() => setConfirmDelete(false)} disabled={pending}>
            Cancelar
          </button>
          <button type="button" className="btn btn-danger" onClick={remove} disabled={pending}>
            Excluir
          </button>
        </div>
      </Dialog>
    </section>
  );
}
