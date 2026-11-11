-- notify_signup.sql - Email the owner when someone NEW signs up.
-- Run once in Supabase: SQL Editor -> New query -> paste this file -> Run.
-- Running it again is safe.
--
-- How it works: when a new row appears in public.profiles (that happens once
-- per person, on their first login), Supabase sends an email via Resend
-- (resend.com) to the owner. Logging in again later sends nothing.
--
-- The Resend API key and the owner's email address are NOT in this file
-- (this repo is public). They are stored in Supabase Vault, an encrypted safe:
--     select vault.create_secret('<your Resend API key>', 'resend_api_key');
--     select vault.create_secret('<your email address>', 'owner_email');
-- Without them, this rule simply does nothing.
--
-- The email is queued and sent in the background (pg_net), so a sign-up
-- never fails or waits because of it.

create extension if not exists pg_net with schema extensions;

create or replace function public.notify_new_signup()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
declare
  api_key text;
  owner   text;
begin
  select decrypted_secret into api_key from vault.decrypted_secrets where name = 'resend_api_key';
  select decrypted_secret into owner   from vault.decrypted_secrets where name = 'owner_email';
  if api_key is null or owner is null then
    return new;                         -- not set up: do nothing
  end if;

  perform net.http_post(
    url     := 'https://api.resend.com/emails',
    headers := jsonb_build_object(
                 'Authorization', 'Bearer ' || api_key,
                 'Content-Type',  'application/json'),
    body    := jsonb_build_object(
                 'from',    'Formula Finder <onboarding@resend.dev>',
                 'to',      jsonb_build_array(owner),
                 'subject', 'New sign-up: ' || coalesce(new.email, '(no email)'),
                 'text',    'Someone new signed up for Formula Finder V2:' || E'\n\n'
                            || '    ' || coalesce(new.email, '(no email)') || E'\n\n'
                            || 'They see "No access yet" until you give access:' || E'\n'
                            || 'Supabase -> Table Editor -> profiles -> set free_access to TRUE.' || E'\n')
  );
  return new;
exception when others then
  return new;                           -- never block a sign-up because of this email
end;
$$;

revoke all on function public.notify_new_signup() from public, anon, authenticated;

drop trigger if exists on_profile_created_notify on public.profiles;
create trigger on_profile_created_notify
  after insert on public.profiles
  for each row execute function public.notify_new_signup();
