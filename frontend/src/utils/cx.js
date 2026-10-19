/** Junta nomes de classe ignorando valores vazios: cx("a", cond && "b") -> "a b". */
export function cx(...parts) {
  return parts.filter(Boolean).join(" ");
}
