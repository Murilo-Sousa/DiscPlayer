import { useState } from "react";
import { cx } from "../utils/cx.js";
import { hueFrom, initials } from "../utils/format.js";

/**
 * Capa do jogo. Tenta a miniatura, depois a imagem original e, se nenhuma
 * carregar (ou o jogo não tiver imagem), mostra um espaço reservado com as
 * iniciais, para a grade nunca ficar com buracos.
 */
export function Cover({ game, ratio = "poster", alt, className, eager = false, original = false }) {
  const sources = [original ? null : game?.cover_thumb_url, game?.cover_url].filter(
    (src, index, all) => src && all.indexOf(src) === index,
  );
  const [failed, setFailed] = useState(0);
  const src = sources[failed];
  const name = game?.name ?? "";

  return (
    <span className={cx("cover", className)} data-ratio={ratio}>
      {src ? (
        <img
          key={src}
          src={src}
          alt={alt ?? ""}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed((count) => count + 1)}
        />
      ) : (
        <span
          className="cover-fallback"
          style={{ "--hue": hueFrom(name) }}
          role={alt ? "img" : undefined}
          aria-label={alt || undefined}
        >
          <span aria-hidden="true">{initials(name)}</span>
        </span>
      )}
    </span>
  );
}

/** Até quatro capas sobrepostas, como uma pilha de caixas de jogo. */
export function CoverStack({ covers = [], className }) {
  const items = covers.slice(0, 4);
  return (
    <span className={cx("cover-stack", className)} data-count={items.length} aria-hidden="true">
      {items.length === 0 ? (
        <span className="cover-stack-empty" />
      ) : (
        items.map((cover, index) => (
          <Cover key={`${cover.name}-${index}`} game={cover} ratio="poster" className="cover-stack-item" />
        ))
      )}
    </span>
  );
}
