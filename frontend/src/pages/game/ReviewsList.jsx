import { useState } from "react";
import { EmptyState, ErrorState } from "../../components/States.jsx";
import { ListSkeleton } from "../../components/Layout.jsx";
import { Pagination } from "../../components/Pagination.jsx";
import { ReviewCard } from "../../components/ReviewCard.jsx";
import { useAuth } from "../../context/AuthContext.jsx";
import { useToast } from "../../context/ToastContext.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { useLocation, useNavigate } from "../../router/index.jsx";
import { gamesApi, reviewsApi } from "../../services/api.js";

const SORTS = [
  { value: "recent", label: "Mais recentes" },
  { value: "popular", label: "Mais curtidas" },
  { value: "highest", label: "Maiores notas" },
  { value: "lowest", label: "Menores notas" },
];

/** Reviews da comunidade para o jogo, com ordenação, paginação e curtidas. */
export function ReviewsList({ rawgId, refreshKey }) {
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const [sort, setSort] = useState("recent");
  const [page, setPage] = useState(1);
  const [pendingId, setPendingId] = useState(null);
  const state = useAsync(
    (signal) => gamesApi.reviews(rawgId, { sort, page, per_page: 10 }, { signal }),
    [rawgId, sort, page, refreshKey],
  );

  const like = async (review) => {
    if (!user) {
      navigate(`/entrar?proximo=${encodeURIComponent(pathname + search)}`);
      return;
    }
    setPendingId(review.id);
    try {
      const result = await (review.liked ? reviewsApi.unlike(review.id) : reviewsApi.like(review.id));
      state.setData((data) => ({
        ...data,
        items: data.items.map((item) => (item.id === review.id ? { ...item, liked: result.liked, like_count: result.like_count } : item)),
      }));
    } catch (error) {
      toast.error(error.message);
    } finally {
      setPendingId(null);
    }
  };

  const data = state.data;
  return (
    <section className="section" aria-labelledby="reviews-title">
      <div className="section-head">
        <h2 id="reviews-title" className="section-title">
          Reviews
        </h2>
        <div className="inline-select">
          <label htmlFor="reviews-sort">Ordenar</label>
          <select
            id="reviews-sort"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value);
              setPage(1);
            }}
          >
            {SORTS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {state.error && !data ? (
        <ErrorState error={state.error} onRetry={state.reload} compact />
      ) : !data ? (
        <ListSkeleton rows={3} />
      ) : data.items.length === 0 ? (
        <EmptyState title="Nenhuma review ainda" compact>
          Ninguém avaliou este jogo no DiscPlayer. Dê a primeira nota.
        </EmptyState>
      ) : (
        <div aria-busy={state.loading || undefined}>
          <div className="review-list">
            {data.items.map((review) => (
              <ReviewCard key={review.id} review={review} canLike={!!user} onLike={like} pending={pendingId === review.id} />
            ))}
          </div>
          <Pagination
            page={page}
            hasNext={data.has_next}
            label="Páginas de reviews"
            onPage={setPage}
          />
        </div>
      )}
    </section>
  );
}
