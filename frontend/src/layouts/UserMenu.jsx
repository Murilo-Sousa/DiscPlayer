import { useCallback, useId, useRef, useState } from "react";
import { Avatar } from "../components/Avatar.jsx";
import { Icon } from "../components/Icon.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useDismiss } from "../hooks/useDismiss.js";
import { Link, useNavigate } from "../router/index.jsx";
import { userPath } from "../utils/format.js";

export function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const menuId = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(rootRef, open, close);

  const signOut = async () => {
    close();
    try {
      await logout();
      navigate("/");
      toast.success("Você saiu da sua conta.");
    } catch (error) {
      toast.error(error.message);
    }
  };

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        className="user-menu-button"
        aria-expanded={open}
        aria-controls={menuId}
        aria-haspopup="true"
        onClick={() => setOpen((value) => !value)}
      >
        <Avatar user={user} size={32} />
        <span className="sr-only">Menu de {user.display_name}</span>
      </button>
      {open && (
        <div className="menu" id={menuId}>
          <p className="menu-heading">
            <strong>{user.display_name}</strong>
            <span>@{user.username}</span>
          </p>
          <Link to={userPath(user.username)} className="menu-item" onClick={close}>
            <Icon name="user" size={18} /> Meu perfil
          </Link>
          <Link to="/diario" className="menu-item" onClick={close}>
            <Icon name="book" size={18} /> Meu diário
          </Link>
          <Link to="/configuracoes" className="menu-item" onClick={close}>
            <Icon name="edit" size={18} /> Configurações
          </Link>
          <button type="button" className="menu-item" onClick={signOut}>
            <Icon name="logout" size={18} /> Sair
          </button>
        </div>
      )}
    </div>
  );
}
