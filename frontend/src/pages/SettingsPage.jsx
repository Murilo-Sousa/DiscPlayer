import { useState } from "react";
import { Avatar } from "../components/Avatar.jsx";
import { Field } from "../components/Field.jsx";
import { PageHeader } from "../components/Layout.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useDebounced } from "../hooks/useDebounced.js";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link } from "../router/index.jsx";
import { userPath } from "../utils/format.js";

export default function SettingsPage() {
  useDocumentTitle("Configurações");
  const { user, updateProfile } = useAuth();
  const toast = useToast();
  const [values, setValues] = useState({
    display_name: user.display_name ?? "",
    bio: user.bio ?? "",
    avatar_url: user.avatar_url ?? "",
  });
  const [errors, setErrors] = useState({});
  const [pending, setPending] = useState(false);

  const set = (key) => (event) => setValues((current) => ({ ...current, [key]: event.target.value }));
  const dirty =
    values.display_name !== (user.display_name ?? "") ||
    values.bio !== (user.bio ?? "") ||
    values.avatar_url !== (user.avatar_url ?? "");

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!values.display_name.trim()) found.display_name = "O nome de exibição é obrigatório.";
    if (values.avatar_url.trim() && !/^https:\/\//i.test(values.avatar_url.trim())) {
      found.avatar_url = "Use um endereço que comece com https://.";
    }
    setErrors(found);
    if (Object.keys(found).length) return;
    setPending(true);
    try {
      const saved = await updateProfile({
        display_name: values.display_name.trim(),
        bio: values.bio.trim() || null,
        avatar_url: values.avatar_url.trim() || null,
      });
      setValues({ display_name: saved.display_name, bio: saved.bio ?? "", avatar_url: saved.avatar_url ?? "" });
      toast.success("Perfil atualizado.");
    } catch (error) {
      setErrors(error.fields ?? {});
      if (!error.fields) toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  // A foto só é carregada depois que a pessoa para de digitar, para não pedir um endereço pela metade a cada tecla.
  const previewPhoto = useDebounced(values.avatar_url.trim(), 600);
  const preview = { ...user, display_name: values.display_name || user.username, avatar_url: previewPhoto || null };

  return (
    <div className="container page page-narrow">
      <PageHeader
        title="Configurações"
        lead="Como as outras pessoas veem você no DiscPlayer."
        actions={
          <Link to={userPath(user.username)} className="btn">
            Ver meu perfil
          </Link>
        }
      />
      <form className="form settings-form" onSubmit={submit} noValidate>
        <div className="settings-preview">
          <Avatar key={preview.avatar_url ?? "none"} user={preview} size={64} />
          <div>
            <p className="settings-name">{preview.display_name}</p>
            <p className="muted">@{user.username}</p>
          </div>
        </div>
        <Field label="Nome de exibição" maxLength={50} value={values.display_name} onChange={set("display_name")} error={errors.display_name} />
        <Field label="Bio" as="textarea" rows={4} maxLength={280} value={values.bio} onChange={set("bio")} error={errors.bio} hint="Até 280 caracteres. Aparece no seu perfil público." />
        <Field label="Endereço da foto" type="url" inputMode="url" value={values.avatar_url} onChange={set("avatar_url")} error={errors.avatar_url} hint="Link direto para uma imagem. Sem foto, usamos suas iniciais." />
        <dl className="settings-readonly">
          <div>
            <dt>Nome de usuário</dt>
            <dd>@{user.username}</dd>
          </div>
          <div>
            <dt>E-mail</dt>
            <dd>{user.email}</dd>
          </div>
        </dl>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={pending || !dirty}>
            {pending ? "Salvando…" : "Salvar alterações"}
          </button>
        </div>
      </form>
    </div>
  );
}
