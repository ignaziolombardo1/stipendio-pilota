-- Stipendio Pilota: codice di recupero password.
-- Incolla tutto in Supabase > SQL Editor > Run (una volta sola).
create extension if not exists pgcrypto with schema extensions;

create table if not exists public.sp_recovery (
  user_id uuid primary key references auth.users(id) on delete cascade,
  code_hash text not null,
  updated_at timestamptz not null default now()
);
alter table public.sp_recovery enable row level security;
-- Nessuna policy: la tabella si usa solo tramite le due funzioni qui sotto.

create or replace function public.sp_set_recovery(p_code text)
returns boolean language plpgsql security definer
set search_path = public, extensions, auth as $$
begin
  if auth.uid() is null or length(coalesce(p_code, '')) < 16 then return false; end if;
  insert into public.sp_recovery (user_id, code_hash)
  values (auth.uid(), crypt(upper(p_code), gen_salt('bf')))
  on conflict (user_id) do update set code_hash = excluded.code_hash, updated_at = now();
  return true;
end $$;

create or replace function public.sp_reset_pw(p_email text, p_code text, p_new text)
returns boolean language plpgsql security definer
set search_path = public, extensions, auth as $$
declare uid uuid; h text;
begin
  if length(coalesce(p_new, '')) < 6 then return false; end if;
  select id into uid from auth.users where lower(email) = lower(p_email);
  if uid is null then perform pg_sleep(0.6); return false; end if;
  select code_hash into h from public.sp_recovery where user_id = uid;
  if h is null or crypt(upper(p_code), h) <> h then perform pg_sleep(0.6); return false; end if;
  update auth.users set encrypted_password = crypt(p_new, gen_salt('bf')), updated_at = now() where id = uid;
  return true;
end $$;

revoke all on function public.sp_set_recovery(text) from public, anon;
revoke all on function public.sp_reset_pw(text, text, text) from public;
grant execute on function public.sp_set_recovery(text) to authenticated;
grant execute on function public.sp_reset_pw(text, text, text) to anon, authenticated;
