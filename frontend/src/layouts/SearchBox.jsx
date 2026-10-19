import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Avatar } from "../components/Avatar.jsx";
import { Cover } from "../components/Cover.jsx";
import { Icon } from "../components/Icon.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { useDebounced } from "../hooks/useDebounced.js";
import { Link, useLocation, useNavigate } from "../router/index.jsx";
import { searchApi } from "../services/api.js";
import { formatYear, gamePath, listPath, plural, userPath } from "../utils/format.js";

export const MIN_QUERY = 2;

/** Transforma a resposta de /api/search em uma lista plana de opções navegáveis por teclado. */
export function buildOptions(data, query) {
  if (!data) return [];
  const options = [
    ...data.games.items.slice(0, 5).map((game) => ({
      key: `g${game.rawg_id}`,
      group: "Jogos",
      label: game.name,
      hint: formatYear(game.released),
      to: gamePath(game),
      game,
    })),
    ...data.users.slice(0, 3).map((user) => ({
      key: `u${user.username}`,
      group: "Jogadores",
      label: user.display_name,
      hint: `@${user.username}`,
      to: userPath(user.username),
      user,
    })),
    ...data.lists.slice(0, 3).map((list) => ({
      key: `l${list.id}`,
      group: "Listas",
      label: list.title,
      hint: plural(list.game_count, "jogo", "jogos"),
      to: listPath(list.id),
    })),
    ...data.reviews.slice(0, 3).map((review) => ({
      key: `r${review.id}`,
      group: "Reviews",
      label: `${review.user.display_name} sobre ${review.game.name}`,
      hint: review.excerpt,
      to: gamePath(review.game),
    })),
  ];
  options.push({
    key: "all",
    group: null,
    label: `Ver todos os resultados para “${query}”`,
    to: `/buscar?q=${encodeURIComponent(query)}`,
  });
  return options;
}

export function SearchBox({ className }) {
  const id = useId();
  const listId = `${id}-list`;
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const rootRef = useRef(null);
  const [value, setValue] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);

  const typed = value.trim();
  const term = useDebounced(typed, 300);
  const enabled = term.length >= MIN_QUERY;
  const state = useAsync(
    (signal) => (enabled ? searchApi.search(term, { signal }) : Promise.resolve(null)),
    [term],
  );
  const options = useMemo(() => buildOptions(state.data, term), [state.data, term]);
  const waiting = typed.length >= MIN_QUERY && (typed !== term || state.loading);

  useEffect(() => {
    setOpen(false);
    setActive(-1);
  }, [pathname]);

  useEffect(() => {
    const onPointer = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, []);

  const showPanel = open && typed.length >= MIN_QUERY;

  const onKeyDown = (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!options.length) return;
      event.preventDefault();
      setOpen(true);
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + options.length) % options.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (active >= 0 && options[active]) navigate(options[active].to);
      else if (typed.length >= MIN_QUERY) navigate(`/buscar?q=${encodeURIComponent(typed)}`);
    } else if (event.key === "Escape") {
      setOpen(false);
      setActive(-1);
    }
  };

  let lastGroup = null;
  return (
    <div className={`search ${className ?? ""}`.trim()} ref={rootRef} role="search">
      <label htmlFor={id} className="sr-only">
        Pesquisar jogos, jogadores, listas e reviews
      </label>
      <Icon name="search" size={18} className="search-icon" />
      <input
        id={id}
        className="search-input"
        type="search"
        autoComplete="off"
        spellCheck="false"
        placeholder="Pesquisar no DiscPlayer"
        maxLength={100}
        value={value}
        role="combobox"
        aria-expanded={showPanel}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${id}-opt-${active}` : undefined}
        onChange={(event) => {
          setValue(event.target.value);
          setActive(-1);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      {showPanel && (
        <div className="search-panel">
          <ul className="search-list" id={listId} role="listbox" aria-label="Resultados da pesquisa" onMouseDown={(event) => event.preventDefault()}>
            {options.map((option, index) => {
              const heading = option.group && option.group !== lastGroup ? option.group : null;
              lastGroup = option.group ?? lastGroup;
              return (
                <li key={option.key} role="presentation">
                  {heading && <p className="search-group">{heading}</p>}
                  <Link
                    to={option.to}
                    id={`${id}-opt-${index}`}
                    role="option"
                    aria-selected={index === active}
                    className="search-option"
                    data-all={option.key === "all" || undefined}
                    onMouseEnter={() => setActive(index)}
                  >
                    {option.game && <Cover game={option.game} ratio="square" className="search-thumb" />}
                    {option.user && <Avatar user={option.user} size={32} />}
                    <span className="search-option-text">
                      <span className="search-option-label">{option.label}</span>
                      {option.hint && <span className="search-option-hint">{option.hint}</span>}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
          <div className="search-status" aria-live="polite">
            {waiting && <p>Buscando…</p>}
            {!waiting && state.error && <p role="alert">{state.error.message}</p>}
            {!waiting && state.data?.games.error && <p>A busca de jogos está indisponível agora. Os outros resultados continuam valendo.</p>}
            {!waiting && state.data && options.length === 1 && !state.error && <p>Nada encontrado para “{term}”.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
