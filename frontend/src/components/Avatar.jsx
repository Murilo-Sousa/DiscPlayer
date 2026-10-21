import { useState } from "react";
import { assetUrl } from "../services/http.js";
import { cx } from "../utils/cx.js";
import { hueFrom, initials, isAvatarPath } from "../utils/format.js";

/** Foto do usuário ou, sem foto, as iniciais sobre uma cor derivada do nome de usuário (cada pessoa tem a sua). */
export function Avatar({ user, size = 36, className }) {
  // Guarda QUAL foto falhou (e não "alguma"): ao trocar de foto, a nova tem a sua chance de carregar.
  const [brokenUrl, setBrokenUrl] = useState(null);
  const label = user?.display_name || user?.username || "";
  const url = user?.avatar_url;
  const showImage = isAvatarPath(url) && brokenUrl !== url;
  return (
    <span
      className={cx("avatar", className)}
      style={{ "--size": `${size}px`, "--hue": hueFrom(user?.username) }}
      aria-hidden="true"
    >
      {showImage ? (
        <img src={assetUrl(url)} alt="" width={size} height={size} loading="lazy" onError={() => setBrokenUrl(url)} />
      ) : (
        <span className="avatar-initials">{initials(label)}</span>
      )}
    </span>
  );
}
