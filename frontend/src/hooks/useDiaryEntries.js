import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { libraryApi } from "../services/api.js";

const MAX_IDS = 80; // o limite da API

/** Tira de `entries` os jogos de `ids` (para recolocar só o que o servidor confirmou). */
function without(entries, ids) {
  const next = { ...entries };
  for (const id of ids) delete next[id];
  return next;
}

/**
 * O que o diário de quem está logado sabe sobre uma lista de jogos, para os cards mostrarem o status e o
 * favorito, e o atalho "guardar na fila".
 *
 * `enabled` só fica verdadeiro depois que o servidor respondeu sobre estes jogos: sem saber o que já está no
 * diário, o atalho não é oferecido. Mesmo assim o servidor só aceita criar (nunca muda um jogo que já existe).
 */
export function useDiaryEntries(rawgIds) {
  const { user } = useAuth();
  const toast = useToast();
  const key = [...new Set(rawgIds)]
    .filter((id) => Number.isInteger(id))
    .sort((a, b) => a - b)
    .slice(0, MAX_IDS)
    .join(",");
  const [entries, setEntries] = useState({});
  const [loadedKey, setLoadedKey] = useState("");
  const [pending, setPending] = useState({});

  const load = useCallback((ids, signal) => {
    return libraryApi.statuses(ids, { signal }).then(({ items }) => {
      setEntries((current) => ({ ...without(current, ids), ...items }));
    });
  }, []);

  useEffect(() => {
    if (!user || !key) {
      setEntries({});
      setLoadedKey("");
      return undefined;
    }
    const controller = new AbortController();
    load(key.split(",").map(Number), controller.signal).then(
      () => {
        if (!controller.signal.aborted) setLoadedKey(key);
      },
      () => {}, // sem os status os cards só não mostram o diário
    );
    return () => controller.abort();
  }, [user?.username, key, load]);

  const add = useCallback(
    async (game) => {
      const id = game.rawg_id;
      setPending((current) => ({ ...current, [id]: true }));
      try {
        const result = await libraryApi.queue(id);
        setEntries((current) => ({ ...current, [id]: { status: result.entry.status, is_favorite: result.entry.is_favorite } }));
        toast.success(`“${game.name}” está na sua fila.`);
      } catch (error) {
        if (error.code === "already_in_diary") {
          toast.error("Este jogo já estava no seu diário. O cartão foi atualizado.");
          load([id]).catch(() => {});
        } else {
          toast.error(error.message);
        }
      } finally {
        setPending((current) => {
          const next = { ...current };
          delete next[id];
          return next;
        });
      }
    },
    [load, toast],
  );

  return { entries, pending, enabled: Boolean(user) && key !== "" && loadedKey === key, add };
}
