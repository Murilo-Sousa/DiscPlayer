import { useEffect, useState } from "react";

/** Devolve `value` só depois de ele ficar `delay` ms sem mudar (evita uma requisição por tecla). */
export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
