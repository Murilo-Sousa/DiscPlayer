import { Disc } from "../components/Disc.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { Link } from "../router/index.jsx";

export default function NotFoundPage({ title = "Página não encontrada", children }) {
  useDocumentTitle(title);
  return (
    <div className="container page not-found">
      <Disc quarters={0} dashed size={72} className="not-found-disc" />
      <h1 className="page-title">{title}</h1>
      <p className="page-lead">{children ?? "O endereço pode ter mudado ou nunca ter existido."}</p>
      <div className="hero-actions">
        <Link to="/" className="btn btn-primary">
          Ir para o início
        </Link>
        <Link to="/jogos" className="btn">
          Explorar jogos
        </Link>
      </div>
    </div>
  );
}
