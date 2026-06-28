-- Active/inactive toggle for services (staff already has is_active). Inactive
-- services are hidden from the consumer + from operational pickers, but remain
-- visible in the barber's management tab so they can be re-activated. Applied to
-- the live project via the Supabase MCP; recorded here to keep repo and DB in sync.

alter table public.services
  add column if not exists is_active boolean not null default true;
