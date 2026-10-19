import { useState } from "react";
import { cx } from "../utils/cx.js";
import { hueFrom, initials, isImageUrl } from "../utils/format.js";

/** Foto do usuário ou, sem foto, as iniciais sobre uma cor derivada do nome de usuário (cada pessoa tem a sua). */
export function Avatar({ user, size = 36, className }) {
  const [broken, setBroken] = useState(false);
  const label = user?.display_name || user?.username || "";
  const showImage = isImageUrl(user?.avatar_url) && !broken;
  return (
    <span
      className={cx("avatar", className)}
      style={{ "--size": `${size}px`, "--hue": hueFrom(user?.username) }}
      aria-hidden="true"
    >
      {showImage ? (
        <img
          src={user.avatar_url}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setBroken(true)}
        />
      ) : (
        <span className="avatar-initials">{initials(label)}</span>
      )}
    </span>
  );
}
