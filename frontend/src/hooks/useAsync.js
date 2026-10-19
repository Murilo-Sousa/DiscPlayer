import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Executa `load(signal)` quando as dependências mudam e acompanha o resultado.
 *
 * status: "loading" | "success" | "error". Durante um recarregamento os dados
 * anteriores continuam disponíveis (a tela não pisca); a requisição anterior é
 * cancelada se as dependências mudarem antes de ela terminar.
 */
export function useAsync(load, deps = []) {
  const [state, setState] = useState({ status: "loading", data: null, error: null });
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    const controller = new AbortController();
    setState((previous) => ({ status: "loading", data: previous.data, error: null }));
    Promise.resolve()
      .then(() => loadRef.current(controller.signal))
      .then(
        (data) => {
          if (!controller.signal.aborted) setState({ status: "success", data, error: null });
        },
        (error) => {
          if (controller.signal.aborted || error?.name === "AbortError") return;
          setState((previous) => ({ status: "error", data: previous.data, error }));
        },
      );
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  const setData = useCallback(
    (updater) =>
      setState((previous) => ({
        ...previous,
        data: typeof updater === "function" ? updater(previous.data) : updater,
      })),
    [],
  );

  return { ...state, loading: state.status === "loading", reload, setData };
}
