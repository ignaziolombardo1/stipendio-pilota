-- Stipendio Pilota: Casa condivisa. Incolla tutto in Supabase > SQL Editor > Run (una volta sola).
create extension if not exists pgcrypto;

create table if not exists sp_casa (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  name text not null default 'Casa',
  created_by uuid not null default auth.uid(),
  created_at timestamptz not null default now()
);
create table if not exists sp_casa_m (
  casa_id uuid not null references sp_casa(id) on delete cascade,
  user_id uuid not null,
  nick text not null default '',
  joined_at timestamptz not null default now(),
  primary key (casa_id, user_id)
);
create table if not exists sp_casa_exp (
  id uuid primary key default gen_random_uuid(),
  casa_id uuid not null references sp_casa(id) on delete cascade,
  user_id uuid not null default auth.uid(),
  day date not null,
  amount numeric(10,2) not null check (amount > 0),
  cat text not null default '',
  note text not null default '',
  created_at timestamptz not null default now()
);
create index if not exists sp_casa_exp_idx on sp_casa_exp (casa_id, day desc);

alter table sp_casa enable row level security;
alter table sp_casa_m enable row level security;
alter table sp_casa_exp enable row level security;

create or replace function sp_casa_is_member(p uuid) returns boolean
language sql security definer stable set search_path = public as $$
  select exists (select 1 from sp_casa_m where casa_id = p and user_id = auth.uid())
$$;

drop policy if exists casa_sel on sp_casa;
create policy casa_sel on sp_casa for select to authenticated using (sp_casa_is_member(id));

drop policy if exists casam_sel on sp_casa_m;
create policy casam_sel on sp_casa_m for select to authenticated using (sp_casa_is_member(casa_id));
drop policy if exists casam_upd on sp_casa_m;
create policy casam_upd on sp_casa_m for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists casam_del on sp_casa_m;
create policy casam_del on sp_casa_m for delete to authenticated using (user_id = auth.uid());

drop policy if exists casae_sel on sp_casa_exp;
create policy casae_sel on sp_casa_exp for select to authenticated using (sp_casa_is_member(casa_id));
drop policy if exists casae_ins on sp_casa_exp;
create policy casae_ins on sp_casa_exp for insert to authenticated with check (user_id = auth.uid() and sp_casa_is_member(casa_id));
drop policy if exists casae_del on sp_casa_exp;
create policy casae_del on sp_casa_exp for delete to authenticated using (user_id = auth.uid());

create or replace function sp_casa_new(p_name text, p_nick text) returns json
language plpgsql security definer set search_path = public as $$
declare v_id uuid; v_code text; n int := 0;
begin
  if auth.uid() is null then raise exception 'accesso richiesto'; end if;
  loop
    v_code := upper(substr(encode(gen_random_bytes(5), 'hex'), 1, 6));
    exit when not exists (select 1 from sp_casa where code = v_code);
    n := n + 1; if n > 20 then raise exception 'riprova'; end if;
  end loop;
  insert into sp_casa (code, name, created_by) values (v_code, coalesce(nullif(trim(p_name), ''), 'Casa'), auth.uid()) returning id into v_id;
  insert into sp_casa_m (casa_id, user_id, nick) values (v_id, auth.uid(), left(coalesce(p_nick, ''), 30));
  return json_build_object('id', v_id, 'code', v_code);
end $$;

create or replace function sp_casa_join(p_code text, p_nick text) returns json
language plpgsql security definer set search_path = public as $$
declare v_id uuid;
begin
  if auth.uid() is null then raise exception 'accesso richiesto'; end if;
  select id into v_id from sp_casa where code = upper(trim(p_code));
  if v_id is null then raise exception 'codice non valido'; end if;
  if (select count(*) from sp_casa_m where casa_id = v_id) >= 4 and not exists (select 1 from sp_casa_m where casa_id = v_id and user_id = auth.uid()) then
    raise exception 'casa al completo';
  end if;
  insert into sp_casa_m (casa_id, user_id, nick) values (v_id, auth.uid(), left(coalesce(p_nick, ''), 30))
    on conflict (casa_id, user_id) do update set nick = excluded.nick;
  return json_build_object('id', v_id);
end $$;

create or replace function sp_casa_leave(p_casa uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  delete from sp_casa_m where casa_id = p_casa and user_id = auth.uid();
  if not exists (select 1 from sp_casa_m where casa_id = p_casa) then delete from sp_casa where id = p_casa; end if;
end $$;

revoke all on function sp_casa_new(text, text), sp_casa_join(text, text), sp_casa_leave(uuid) from public, anon;
grant execute on function sp_casa_new(text, text), sp_casa_join(text, text), sp_casa_leave(uuid), sp_casa_is_member(uuid) to authenticated;
grant select, insert, update, delete on sp_casa, sp_casa_m, sp_casa_exp to authenticated;
