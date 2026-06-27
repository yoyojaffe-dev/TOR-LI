-- Full barbershop-profile dataset: scraped reviews + per-barber services.
-- Foundation only (schema). The enrichment runtime that populates these lands
-- in a separate phase.

-- 1. external_reviews: scraped/aggregated reviews (e.g. Google), kept separate
-- from the in-app `reviews` table (which is keyed to a booking_id + user_token).
create table if not exists public.external_reviews (
    id             uuid primary key default gen_random_uuid(),
    barbershop_id  uuid not null references public.barbershops(id) on delete cascade,
    author         text,
    rating         numeric,
    text           text,
    source         text not null default 'google',
    reviewed_at    timestamptz,
    created_at     timestamptz not null default now()
);

create index if not exists external_reviews_shop_idx
    on public.external_reviews (barbershop_id);

-- Dedup on re-scrape: same shop + source + author + body collapses to one row.
create unique index if not exists external_reviews_dedup_idx
    on public.external_reviews (
        barbershop_id,
        source,
        md5(coalesce(author, '') || '|' || coalesce(text, ''))
    );

alter table public.external_reviews enable row level security;

-- Public read (social proof shown on the shop profile). Writes are service-role
-- only (agents bypass RLS); no anon/authenticated write policy is granted.
drop policy if exists "external_reviews public read" on public.external_reviews;
create policy "external_reviews public read"
    on public.external_reviews for select
    to anon, authenticated
    using (true);

grant select on public.external_reviews to anon, authenticated;
grant select, insert, update, delete on public.external_reviews to service_role;

-- 2. services: per-barber mapping + structured category.
-- staff_id null = a shop-level general service (not tied to one barber).
alter table public.services
    add column if not exists staff_id uuid references public.staff(id) on delete set null;
alter table public.services
    add column if not exists category text;

create index if not exists idx_services_staff_id on public.services (staff_id);

-- 3. Portfolio: no change — barbershops.photo_urls stays; barbers upload real
-- portfolios via the dashboard later.
