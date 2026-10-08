-- Recall by meaning: an embedding per saved solution, searched with pgvector.
--
-- No vector index on purpose: pgvector's index types stop at 2,000
-- dimensions, and a user's few hundred rows scan in milliseconds. Revisit
-- with a halfvec index if a user ever has tens of thousands.

create extension if not exists vector with schema extensions;

alter table public.solutions
  add column embedding extensions.vector(3072),
  -- Which model produced the embedding, so rows can be re-embedded when it
  -- changes.
  add column embedding_model text,
  -- The problem statement, when the save had it (live saves do; imports
  -- don't, yet).
  add column statement text,
  -- When LeetCode accepted it: what "recent" should mean, rather than when
  -- the row was saved, which for an import is an accident of order.
  add column submitted_at timestamptz;

-- The backfill PATCHes embeddings as the user. Column-level grant, so
-- nothing else becomes updatable.
create policy "Users update their own solutions"
  on public.solutions for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

grant update (embedding, embedding_model) on public.solutions to authenticated;

-- Nearest saved solutions to a query vector, nearest first. SECURITY
-- INVOKER: row-level security applies inside, so a caller only ever
-- searches their own rows.
create or replace function public.match_solutions(
  query_embedding extensions.vector(3072),
  match_count int default 20
)
returns table (
  id uuid,
  problem_slug text,
  problem_title text,
  difficulty text,
  topic_tags text[],
  summary text,
  submitted_at timestamptz,
  created_at timestamptz,
  similarity double precision
)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  select s.id, s.problem_slug, s.problem_title, s.difficulty, s.topic_tags,
         s.summary, s.submitted_at, s.created_at,
         1 - (s.embedding <=> query_embedding) as similarity
  from public.solutions s
  where s.embedding is not null
  order by s.embedding <=> query_embedding
  limit match_count
$$;

grant execute on function public.match_solutions(extensions.vector(3072), int) to authenticated;
