import { useEffect, useRef, useState } from "react";
import { Avatar } from "../components/Avatar.jsx";
import { Dialog } from "../components/Dialog.jsx";
import { Field } from "../components/Field.jsx";
import { PageHeader } from "../components/Layout.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link, useNavigate } from "../router/index.jsx";
import { hueFrom, userPath } from "../utils/format.js";

export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const PHOTO_MAX_BYTES = 5 * 1024 * 1024;

/** Confere o arquivo antes de enviar (o servidor confere tudo de novo). Devolve a mensagem de erro ou null. */
export function checkPhotoFile(file) {
  if (!PHOTO_TYPES.includes(file.type)) return "Escolha uma imagem JPG, PNG ou WebP.";
  if (file.size > PHOTO_MAX_BYTES) return "A foto é grande demais. Escolha um arquivo de até 5 MB.";
  if (file.size === 0) return "O arquivo está vazio.";
  return null;
}

function PhotoSection({ user }) {
  const { uploadAvatar, removeAvatar } = useAuth();
  const toast = useToast();
  const input = useRef(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  // A prévia é um endereço temporário do navegador (blob:); ele é liberado ao trocar de arquivo ou sair da página.
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const choose = (event) => {
    const picked = event.target.files?.[0];
    event.target.value = ""; // permite escolher o mesmo arquivo de novo depois de cancelar
    if (!picked) return;
    const problem = checkPhotoFile(picked);
    setError(problem ?? "");
    setFile(problem ? null : picked);
  };

  const cancel = () => {
    setFile(null);
    setError("");
  };

  const save = async () => {
    setPending(true);
    setError("");
    try {
      await uploadAvatar(file);
      setFile(null);
      toast.success("Foto atualizada.");
    } catch (failure) {
      setError(failure.fields?.file ?? failure.message);
    } finally {
      setPending(false);
    }
  };

  const remove = async () => {
    setPending(true);
    setError("");
    try {
      await removeAvatar();
      toast.success("Foto removida. Voltamos a usar as suas iniciais.");
    } catch (failure) {
      setError(failure.message);
    } finally {
      setPending(false);
    }
  };

  return (
    <section className="settings-photo" aria-labelledby="photo-title">
      <h2 id="photo-title" className="settings-section-title">
        Foto de perfil
      </h2>
      <div className="settings-photo-row">
        {previewUrl ? (
          <span className="avatar" style={{ "--size": "96px", "--hue": hueFrom(user.username) }} data-testid="photo-preview">
            <img src={previewUrl} alt="Prévia da nova foto" width={96} height={96} />
          </span>
        ) : (
          <Avatar user={user} size={96} />
        )}
        <div className="settings-photo-main">
          <input
            ref={input}
            type="file"
            accept={PHOTO_TYPES.join(",")}
            hidden
            tabIndex={-1}
            data-testid="photo-input"
            onChange={choose}
          />
          {file ? (
            <>
              <p className="settings-photo-file">{file.name}</p>
              <div className="form-actions">
                <button type="button" className="btn btn-primary" onClick={save} disabled={pending}>
                  {pending ? "Enviando…" : "Salvar foto"}
                </button>
                <button type="button" className="btn btn-quiet" onClick={cancel} disabled={pending}>
                  Cancelar
                </button>
              </div>
            </>
          ) : (
            <div className="form-actions">
              <button type="button" className="btn" onClick={() => input.current?.click()} disabled={pending}>
                {user.avatar_url ? "Trocar foto" : "Escolher foto"}
              </button>
              {user.avatar_url && (
                <button type="button" className="btn btn-quiet link-danger" onClick={remove} disabled={pending}>
                  Remover foto
                </button>
              )}
            </div>
          )}
          <p className="field-hint">
            JPG, PNG ou WebP, até 5 MB. A foto é recortada em quadrado no centro e reduzida; dados escondidos no arquivo, como a
            localização da câmera, são apagados. Sem foto, usamos as suas iniciais.
          </p>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function DeleteAccount() {
  const { deleteAccount } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const close = () => {
    if (pending) return;
    setOpen(false);
    setPassword("");
    setError("");
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!password) {
      setError("Informe a sua senha para confirmar.");
      return;
    }
    setPending(true);
    setError("");
    try {
      await deleteAccount(password, { onDeleted: () => navigate("/", { replace: true }) });
      toast.success("Sua conta foi excluída. Obrigado por ter jogado com a gente.");
    } catch (failure) {
      setError(failure.fields?.password ?? failure.message);
      setPending(false);
    }
  };

  return (
    <section className="danger-zone" aria-labelledby="danger-title">
      <h2 id="danger-title" className="settings-section-title">
        Excluir conta
      </h2>
      <p>
        Apaga a sua conta e tudo o que é seu: diário, jogadas, notas, reviews, listas, curtidas, quem você segue e a sua foto.
        Não dá para desfazer.
      </p>
      <button type="button" className="btn btn-danger" onClick={() => setOpen(true)}>
        Excluir minha conta…
      </button>

      <Dialog open={open} onClose={close} title="Excluir a sua conta?">
        <form onSubmit={submit} noValidate className="form">
          <p>Isto apaga para sempre, e ninguém consegue recuperar:</p>
          <ul className="danger-list">
            <li>o seu diário, as suas jogadas e os seus favoritos;</li>
            <li>as suas notas e reviews (elas saem da média dos jogos);</li>
            <li>as suas listas, as suas curtidas e as pessoas que você segue e que seguem você;</li>
            <li>a sua foto e o seu perfil. O nome de usuário e o e-mail ficam livres para outras pessoas.</li>
          </ul>
          <Field
            label="Digite a sua senha para confirmar"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={error}
            disabled={pending}
          />
          <div className="dialog-actions">
            <button type="button" className="btn" onClick={close} disabled={pending}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-danger" disabled={pending}>
              {pending ? "Excluindo…" : "Excluir definitivamente"}
            </button>
          </div>
        </form>
      </Dialog>
    </section>
  );
}

export default function SettingsPage() {
  useDocumentTitle("Configurações");
  const { user, updateProfile } = useAuth();
  const toast = useToast();
  const [values, setValues] = useState({ display_name: user.display_name ?? "", bio: user.bio ?? "" });
  const [errors, setErrors] = useState({});
  const [pending, setPending] = useState(false);

  const set = (key) => (event) => setValues((current) => ({ ...current, [key]: event.target.value }));
  const dirty = values.display_name !== (user.display_name ?? "") || values.bio !== (user.bio ?? "");

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!values.display_name.trim()) found.display_name = "O nome de exibição é obrigatório.";
    setErrors(found);
    if (Object.keys(found).length) return;
    setPending(true);
    try {
      const saved = await updateProfile({ display_name: values.display_name.trim(), bio: values.bio.trim() || null });
      setValues({ display_name: saved.display_name, bio: saved.bio ?? "" });
      toast.success("Perfil atualizado.");
    } catch (error) {
      setErrors(error.fields ?? {});
      if (!error.fields) toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

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
      <PhotoSection user={user} />
      <form className="form settings-form" onSubmit={submit} noValidate>
        <div className="settings-preview">
          <div>
            <p className="settings-name">{values.display_name || user.username}</p>
            <p className="muted">@{user.username}</p>
          </div>
        </div>
        <Field label="Nome de exibição" maxLength={50} value={values.display_name} onChange={set("display_name")} error={errors.display_name} />
        <Field label="Bio" as="textarea" rows={4} maxLength={280} value={values.bio} onChange={set("bio")} error={errors.bio} hint="Até 280 caracteres. Aparece no seu perfil público." />
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
      <DeleteAccount />
    </div>
  );
}
