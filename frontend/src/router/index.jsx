// Roteador mínimo sobre a History API (sem dependências além do React).
//
// O DiscPlayer tem poucas rotas e nenhuma precisa de aninhamento, então este
// módulo cobre só o que a aplicação usa: rotas com parâmetros (/jogos/:id),
// Link/NavLink, navegação programática, parâmetros de busca e redirecionamento.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const LocationContext = createContext(null);
const ParamsContext = createContext({});

function readLocation() {
  const { pathname, search, hash } = window.location;
  return { pathname, search, hash };
}

const splitPath = (path) => path.split("/").filter(Boolean);

/** Compara um padrão ("/jogos/:id") com um caminho. Devolve os parâmetros ou null. */
export function matchPath(pattern, pathname) {
  if (pattern === "*") return {};
  const wanted = splitPath(pattern);
  const actual = splitPath(pathname);
  if (wanted.length !== actual.length) return null;
  const params = {};
  for (let i = 0; i < wanted.length; i += 1) {
    if (wanted[i].startsWith(":")) {
      try {
        params[wanted[i].slice(1)] = decodeURIComponent(actual[i]);
      } catch {
        return null; // %XX inválido na URL
      }
    } else if (wanted[i] !== actual[i]) {
      return null;
    }
  }
  return params;
}

const isExternal = (to) => /^([a-z][a-z0-9+.-]*:|\/\/)/i.test(to);

export function Router({ children }) {
  const [location, setLocation] = useState(readLocation);

  useEffect(() => {
    const onPop = () => setLocation(readLocation());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to, { replace = false } = {}) => {
    if (isExternal(to)) {
      window.location.assign(to);
      return;
    }
    const url = new URL(to, window.location.href);
    const next = url.pathname + url.search + url.hash;
    const current = window.location.pathname + window.location.search + window.location.hash;
    if (next !== current) {
      window.history[replace ? "replaceState" : "pushState"](null, "", next);
      setLocation(readLocation());
    }
    if (!replace) window.scrollTo(0, 0);
  }, []);

  const value = useMemo(() => ({ ...location, navigate }), [location, navigate]);
  return <LocationContext.Provider value={value}>{children}</LocationContext.Provider>;
}

function useRouterContext() {
  const value = useContext(LocationContext);
  if (!value) throw new Error("Use este hook dentro de <Router>.");
  return value;
}

export const useLocation = () => {
  const { pathname, search, hash } = useRouterContext();
  return { pathname, search, hash };
};
export const useNavigate = () => useRouterContext().navigate;
export const useParams = () => useContext(ParamsContext);

/** Primeira rota cujo padrão combina com o caminho atual; a página é recriada a cada caminho novo. */
export function Routes({ routes }) {
  const { pathname } = useLocation();
  for (const route of routes) {
    const params = matchPath(route.path, pathname);
    if (params) {
      return (
        <ParamsContext.Provider value={params} key={pathname}>
          {route.element}
        </ParamsContext.Provider>
      );
    }
  }
  return null;
}

export function Link({ to, replace = false, onClick, target, children, ...rest }) {
  const navigate = useNavigate();
  const handleClick = (event) => {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      (target && target !== "_self") ||
      isExternal(to)
    ) {
      return;
    }
    event.preventDefault();
    navigate(to, { replace });
  };
  return (
    <a href={to} target={target} onClick={handleClick} {...rest}>
      {children}
    </a>
  );
}

/** Link que sabe se aponta para a página atual (aria-current="page"). */
export function NavLink({ to, end = false, className, children, ...rest }) {
  const { pathname } = useLocation();
  const target = to.split(/[?#]/)[0];
  const active = end || target === "/" ? pathname === target : pathname === target || pathname.startsWith(`${target}/`);
  const resolved = typeof className === "function" ? className({ isActive: active }) : className;
  return (
    <Link to={to} className={resolved} aria-current={active ? "page" : undefined} {...rest}>
      {children}
    </Link>
  );
}

export function Navigate({ to, replace = true }) {
  const navigate = useNavigate();
  useEffect(() => {
    navigate(to, { replace });
  }, [navigate, to, replace]);
  return null;
}

/** Lê e grava os parâmetros de busca da URL (?q=...&pagina=2). Valores vazios saem da URL. */
export function useSearchParams() {
  const { search } = useLocation();
  const navigate = useNavigate();
  const params = useMemo(() => new URLSearchParams(search), [search]);
  const setParams = useCallback(
    (next, { replace = false } = {}) => {
      const source = typeof next === "function" ? next(new URLSearchParams(window.location.search)) : next;
      const entries = source instanceof URLSearchParams ? [...source.entries()] : Object.entries(source);
      const query = new URLSearchParams(
        entries.filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== false).map(([k, v]) => [k, String(v)]),
      ).toString();
      navigate(window.location.pathname + (query ? `?${query}` : ""), { replace });
    },
    [navigate],
  );
  return [params, setParams];
}
