/**
 * Marca discreta para perfis de exemplo (contas fictícias criadas por `python -m app.demo seed`).
 * Não renderiza nada para contas reais, então pode ficar ao lado de qualquer nome.
 */
export function DemoBadge({ user, className }) {
  if (!user?.is_demo) return null;
  return (
    <span className={className ? `demo-badge ${className}` : "demo-badge"} title="Perfil fictício, criado para mostrar o site com atividade.">
      Exemplo
    </span>
  );
}
