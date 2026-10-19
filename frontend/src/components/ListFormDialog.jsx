import { useEffect, useState } from "react";
import { useToast } from "../context/ToastContext.jsx";
import { listsApi } from "../services/api.js";
import { Dialog } from "./Dialog.jsx";
import { Field } from "./Field.jsx";

/** Criar ou editar uma lista (título, descrição e visibilidade). Com `list`, edita; sem, cria. */
export function ListFormDialog({ open, onClose, list, onSaved }) {
  const toast = useToast();
  const [values, setValues] = useState({ title: "", description: "", is_public: true });
  const [errors, setErrors] = useState({});
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (open) {
      setValues({ title: list?.title ?? "", description: list?.description ?? "", is_public: list?.is_public ?? true });
      setErrors({});
    }
  }, [open, list]);

  const submit = async (event) => {
    event.preventDefault();
    if (!values.title.trim()) {
      setErrors({ title: "Dê um título para a lista." });
      return;
    }
    setPending(true);
    setErrors({});
    const payload = { title: values.title.trim(), description: values.description.trim() || null, is_public: values.is_public };
    try {
      const result = list ? await listsApi.update(list.id, payload) : await listsApi.create(payload);
      toast.success(list ? "Lista atualizada." : "Lista criada.");
      onSaved(result.list);
    } catch (error) {
      setErrors(error.fields ?? {});
      if (!error.fields) toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onClose={() => !pending && onClose()} title={list ? "Editar lista" : "Nova lista"}>
      <form className="form" onSubmit={submit} noValidate>
        <Field label="Título" maxLength={80} value={values.title} onChange={(event) => setValues({ ...values, title: event.target.value })} error={errors.title} autoFocus />
        <Field
          label="Descrição (opcional)"
          as="textarea"
          rows={3}
          maxLength={500}
          value={values.description}
          onChange={(event) => setValues({ ...values, description: event.target.value })}
          error={errors.description}
        />
        <fieldset className="field radio-group">
          <legend className="field-label">Quem pode ver</legend>
          <label className="check-inline">
            <input type="radio" name="visibility" checked={values.is_public} onChange={() => setValues({ ...values, is_public: true })} />
            <span>Pública: aparece no seu perfil e na busca</span>
          </label>
          <label className="check-inline">
            <input type="radio" name="visibility" checked={!values.is_public} onChange={() => setValues({ ...values, is_public: false })} />
            <span>Privada: só você vê</span>
          </label>
        </fieldset>
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose} disabled={pending}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={pending}>
            {pending ? "Salvando…" : list ? "Salvar" : "Criar lista"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
