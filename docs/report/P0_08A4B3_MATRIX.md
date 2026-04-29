# P0-08A4B3 matrix

Asset repository:
- get_media_asset: yes
- upsert_media_asset: yes
- find_by_telegram_file_unique_id: yes
- list_media_assets_by_ids: yes
- old/new fields mapped: yes

Link repository:
- get_media_link: yes
- attach_media: yes
- list_media_links: yes
- list_media_for_owner: yes
- set_primary_media: yes
- remove_media_link: yes

Behavior:
- primary media one-per-owner-role: yes
- asset remains after link removal: yes
- owner listing sorted: yes
- Telegram identifiers stored only, no API calls: yes

DB:
- DB-backed tests run: yes
- DB skip documented: yes

Truth boundary:
- no Alembic: yes
- no migrations: yes
- no upload/UI/service claims: yes

Regression:
- B3 tests: pass
- B2/B1 tests: pass
- A4A tests: pass
- A3/A2/A1 tests: pass
- care/recommendation: passed count = 4
- patient/booking: passed count = 4
