import { useAuth } from "../context/AuthContext.jsx";
import { Navigate, useLocation } from "../router/index.jsx";
import { Loader } from "./States.jsx";

/** Só mostra a página a quem está logado; os demais vão para o login e voltam depois. */
export function RequireAuth({ children }) {
  const { user, ready } = useAuth();
  const { pathname, search } = useLocation();
  if (!ready) {
    return (
      <div className="page-loading">
        <Loader label="Verificando sua sessão" />
      </div>
    );
  }
  if (!user) return <Navigate to={`/entrar?proximo=${encodeURIComponent(pathname + search)}`} />;
  return children;
}
