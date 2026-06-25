"""The three autonomous agents that drive Tor-li.

Discovery -> finds barbershops (Google Maps) and writes ``barbershops``.
Scraping  -> reads barbershop URLs, scrapes booking pages (Playwright), parses
             them with OpenAI, writes ``available_slots``.
Booking   -> on-demand, submits a reservation on the barber's own site.

Supabase is the shared message board between all three.
"""
