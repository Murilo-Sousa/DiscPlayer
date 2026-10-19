import { useState } from "react";
import { Field } from "../components/Field.jsx";
import { Logo } from "../components/Logo.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link, Navigate, useNavigate, useSearchParams } from "../router/index.jsx";

/** Só aceita caminhos internos como destino depois do login (evita redirecionar para outro site). */
export function safeNext(value) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/";
  return value;
}

function AuthLayout({ title, lead, children, footer }) {
  return (
    <div className="container page auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <Logo size={26} />
        </div>
        <h1 className="auth-title">{title}</h1>
        {lead && <p className="auth-lead">{lead}</p>}
        {children}
        <p className="auth-footer">{footer}</p>
      </div>
    </div>
  );
}

function FormError({ message }) {
  if (!message) return null;
  return (
    <p className="form-error" role="alert">
      {message}
    </p>
  );
}

export function LoginPage() {
  useDocumentTitle("Entrar");
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [params] = useSearchParams();
  const next = safeNext(params.get("proximo"));
  const [values, setValues] = useState({ identifier: "", password: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [pending, setPending] = useState(false);

  if (user && !pending) return <Navigate to={next} />;

  const set = (key) => (event) => setValues((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    const found = {};
    if (!values.identifier.trim()) found.identifier = "Informe seu e-mail ou nome de usuário.";
    if (!values.password) found.password = "Informe sua senha.";
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length) return;
    setPending(true);
    try {
      const account = await login({ identifier: values.identifier.trim(), password: values.password });
      toast.success(`Bem-vindo de volta, ${account.display_name}.`);
      navigate(next, { replace: true });
    } catch (error) {
      setErrors(error.fields ?? {});
      setFormError(error.fields ? "" : error.message);
      setPending(false);
    }
  };

  return (
    <AuthLayout
      title="Entrar"
      lead="Acesse seu diário, suas listas e o que a comunidade anda jogando."
      footer={
        <>
          Ainda não tem conta? <Link to={`/cadastro${next !== "/" ? `?proximo=${encodeURIComponent(next)}` : ""}`}>Criar conta</Link>
        </>
      }
    >
      <form className="form" onSubmit={submit} noValidate>
        <FormError message={formError} />
        <Field label="E-mail ou usuário" name="identifier" autoComplete="username" autoFocus value={values.identifier} onChange={set("identifier")} error={errors.identifier} />
        <Field label="Senha" name="password" type="password" autoComplete="current-password" value={values.password} onChange={set("password")} error={errors.password} />
        <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
          {pending ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </AuthLayout>
  );
}

export function RegisterPage() {
  useDocumentTitle("Criar conta");
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [params] = useSearchParams();
  const next = safeNext(params.get("proximo"));
  const [values, setValues] = useState({ display_name: "", username: "", email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [pending, setPending] = useState(false);

  if (user && !pending) return <Navigate to={next} />;

  const set = (key) => (event) => setValues((current) => ({ ...current, [key]: event.target.value }));

  const validate = () => {
    const found = {};
    if (!/^[A-Za-z0-9_]{3,24}$/.test(values.username.trim())) {
      found.username = "Use de 3 a 24 caracteres: letras, números e _ (sem espaços).";
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) found.email = "Informe um e-mail válido.";
    if (values.password.length < 8) found.password = "A senha precisa ter pelo menos 8 caracteres.";
    return found;
  };

  const submit = async (event) => {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    setFormError("");
    if (Object.keys(found).length) return;
    setPending(true);
    try {
      const payload = { username: values.username.trim().toLowerCase(), email: values.email.trim(), password: values.password };
      if (values.display_name.trim()) payload.display_name = values.display_name.trim();
      const account = await register(payload);
      toast.success(`Conta criada. Bem-vindo, ${account.display_name}.`);
      navigate(next === "/" ? "/jogos" : next, { replace: true });
    } catch (error) {
      setErrors(error.fields ?? {});
      setFormError(error.fields ? "" : error.message);
      setPending(false);
    }
  };

  return (
    <AuthLayout
      title="Criar conta"
      lead="Comece o seu diário de jogos. É de graça."
      footer={
        <>
          Já tem conta? <Link to={`/entrar${next !== "/" ? `?proximo=${encodeURIComponent(next)}` : ""}`}>Entrar</Link>
        </>
      }
    >
      <form className="form" onSubmit={submit} noValidate>
        <FormError message={formError} />
        <Field label="Nome de exibição (opcional)" name="display_name" autoComplete="name" maxLength={50} value={values.display_name} onChange={set("display_name")} error={errors.display_name} />
        <Field
          label="Nome de usuário"
          name="username"
          autoComplete="username"
          maxLength={24}
          hint="Letras, números e _. Fica em minúsculas e aparece no endereço do seu perfil."
          value={values.username}
          onChange={set("username")}
          error={errors.username}
        />
        <Field label="E-mail" name="email" type="email" autoComplete="email" value={values.email} onChange={set("email")} error={errors.email} hint="Usado só para entrar. Não aparece no seu perfil." />
        <Field label="Senha" name="password" type="password" autoComplete="new-password" value={values.password} onChange={set("password")} error={errors.password} hint="Pelo menos 8 caracteres." />
        <button type="submit" className="btn btn-primary btn-block" disabled={pending}>
          {pending ? "Criando…" : "Criar conta"}
        </button>
      </form>
    </AuthLayout>
  );
}
