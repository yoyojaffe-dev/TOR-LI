-- Publish the bookings table for Supabase Realtime so the barber dashboard
-- receives live new-booking alerts (toast + header badge). RLS still applies:
-- an authenticated owner only receives Realtime events for their own shop's
-- bookings. Applied to the live project via the Supabase MCP.
alter publication supabase_realtime add table public.bookings;
