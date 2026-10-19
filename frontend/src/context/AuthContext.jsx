import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { authApi } from "../services/api.js";
import { setCsrfToken } from "../services/http.js";

const AuthContext = createContext(null);

/**
 * Estado de autenticação. A sessão em si é um cookie HttpOnly; aqui só guardamos
 * o perfil do usuário (sem senha) para decidir o que mostrar.
 */
export function AuthProvider({ children }) {
  const [state, setState] = useState({ user: null, ready: false });

  useEffect(() => {
    const controller = new AbortController();
    authApi
      .me({ signal: controller.signal })
      .then((data) => {
        setCsrfToken(data.csrf_token);
        setState({ user: data.user, ready: true });
      })
      .catch((error) => {
        if (error?.name !== "AbortError") setState({ user: null, ready: true });
      });
    return () => controller.abort();
  }, []);

  const adopt = useCallback((data) => {
    setCsrfToken(data.csrf_token);
    setState({ user: data.user, ready: true });
    return data.user;
  }, []);

  const login = useCallback((credentials) => authApi.login(credentials).then(adopt), [adopt]);
  const register = useCallback((fields) => authApi.register(fields).then(adopt), [adopt]);
  const logout = useCallback(() => authApi.logout().then(adopt), [adopt]);
  const updateProfile = useCallback(
    (changes) =>
      authApi.updateProfile(changes).then((data) => {
        setState((previous) => ({ ...previous, user: data.user }));
        return data.user;
      }),
    [],
  );

  const value = useMemo(
    () => ({ user: state.user, ready: state.ready, login, register, logout, updateProfile }),
    [state, login, register, logout, updateProfile],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth precisa de <AuthProvider>.");
  return value;
}
