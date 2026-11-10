-- schema.sql - The Formula Finder V2 database. Run this once in Supabase:
-- Dashboard -> SQL Editor -> New query -> paste this whole file -> Run.
-- Running it again is safe: it only (re)creates what is missing or changed.
--
-- Two tables:
--   cards     every formula card (filled by tools/upload_cards.py)
--   profiles  one row per user: email, free_access, paid_until, dates
--
-- Who can see what (Row Level Security):
--   - nobody who is not logged in can read anything;
--   - a logged-in user can read their OWN profile, and cannot change it
--     (otherwise anyone could give themselves free access);
--   - a logged-in user can read the cards only if their profile has
--     free_access = true, or paid_until is later than now.
--   You (the owner) change profiles in Table Editor; the upload script uses
--   the secret key, which skips these rules.


-- ---------- cards ----------
create table if not exists public.cards (
  id                  text primary key,     -- e.g. "calculus-integration-by-parts"
  position            integer not null,     -- order in the app
  tab                 text not null,        -- e.g. "math"
  tab_name            text not null,        -- e.g. "Math"
  tab_title           text,
  chapter             text not null,        -- e.g. "math-chapter-calculus"
  chapter_name        text not null,        -- e.g. "Calculus"
  chapter_source      text,                 -- e.g. "math/00_calculus.tex"
  section             text not null,
  section_title_html  text,
  section_title_text  text,
  section_color       text,
  section_intro_html  text,
  title_html          text,
  title_text          text,
  body_html           text,
  body_text           text,
  latex               text,
  uploaded_at         timestamptz not null default now()
);


-- ---------- profiles ----------
create table if not exists public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  email        text,
  free_access  boolean not null default false,   -- tick this to let someone in
  paid_until   timestamptz,                      -- set by the payment (later)
  created_at   timestamptz not null default now(),
  last_seen    timestamptz                       -- last time they opened the app
);

-- Every new sign-up gets a profile automatically (no access yet).
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, email) values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();


-- ---------- access check ----------
-- true when the logged-in user may see the cards.
create or replace function public.has_access()
returns boolean
language sql stable
security definer set search_path = ''
as $$
  select exists (
    select 1 from public.profiles p
    where p.id = (select auth.uid())
      and (p.free_access or p.paid_until > now())
  );
$$;

-- The app calls this when it opens, so you can see who uses it. It can only
-- change last_seen of the user who calls it, nothing else.
create or replace function public.touch_last_seen()
returns void
language sql
security definer set search_path = ''
as $$
  update public.profiles set last_seen = now() where id = (select auth.uid());
$$;


-- ---------- rules ----------
alter table public.cards    enable row level security;
alter table public.profiles enable row level security;

drop policy if exists "members read cards" on public.cards;
create policy "members read cards" on public.cards
  for select to authenticated
  using ((select public.has_access()));

drop policy if exists "read own profile" on public.profiles;
create policy "read own profile" on public.profiles
  for select to authenticated
  using (id = (select auth.uid()));

-- Who may use the tables at all (the rules above then filter the rows).
revoke all on public.cards, public.profiles from anon, authenticated;
grant select on public.cards, public.profiles to authenticated;
grant all on public.cards, public.profiles to service_role;

revoke all on function public.has_access()      from public, anon;
revoke all on function public.touch_last_seen() from public, anon;
revoke all on function public.handle_new_user() from public, anon, authenticated;
grant execute on function public.has_access()      to authenticated;
grant execute on function public.touch_last_seen() to authenticated;
