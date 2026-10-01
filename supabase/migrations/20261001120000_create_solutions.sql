-- Accepted LeetCode submissions, and a short summary of each.
--
-- Rows are written by the backend using the signed-in user's own access token,
-- so the policies below are what decide who can read and write what. There is
-- no service-role path into this table.

create table public.solutions (
  id uuid primary key default gen_random_uuid(),

  -- Filled in from the caller's token, so a row can only ever belong to
  -- whoever inserted it.
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,

  -- LeetCode's id for the submission. Already past the 32-bit range.
  submission_id bigint not null,

  problem_slug text not null,
  problem_title text,
  problem_number text,
  difficulty text,
  topic_tags text[] not null default '{}',

  language text,
  -- The code LeetCode accepted. Kept so the summary can be regenerated when
  -- the way it is written improves.
  code text not null,

  summary text not null,
  -- Which model wrote the summary.
  summary_model text,

  created_at timestamptz not null default now(),

  -- Saving is idempotent: the same submission is stored once per user. The
  -- index behind this constraint also serves lookups by user.
  unique (user_id, submission_id)
);

alter table public.solutions enable row level security;

create policy "Users read their own solutions"
  on public.solutions for select
  to authenticated
  using ((select auth.uid()) = user_id);

create policy "Users insert their own solutions"
  on public.solutions for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

-- No update or delete yet: nothing needs them, so nothing is allowed them.
grant select, insert on public.solutions to authenticated;
