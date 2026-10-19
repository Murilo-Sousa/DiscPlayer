import { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useLocation, useNavigate } from "../router/index.jsx";
import { usersApi } from "../services/api.js";

/** Seguir/deixar de seguir. Quem não está logado é levado ao login. */
export function FollowButton({ username, following, onChange }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const toast = useToast();
  const [pending, setPending] = useState(false);

  const toggle = async () => {
    if (!user) {
      navigate(`/entrar?proximo=${encodeURIComponent(pathname + search)}`);
      return;
    }
    setPending(true);
    try {
      const result = await (following ? usersApi.unfollow(username) : usersApi.follow(username));
      onChange(result);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setPending(false);
    }
  };

  return (
    <button type="button" className={following ? "btn" : "btn btn-primary"} aria-pressed={following} disabled={pending} onClick={toggle}>
      {following ? "Seguindo" : "Seguir"}
    </button>
  );
}
