# Analyst access to the production database

Lets a data analyst query the production MySQL database directly (e.g. from
Google Colab) for offline analysis of radio packet data, without exposing
MySQL to the internet and without giving them a full server shell.

`db` in `docker-compose.yml` binds MySQL to `127.0.0.1:3306` on the host --
reachable only from the server itself, never from the internet, even if the
host firewall is misconfigured. The analyst reaches it through an SSH tunnel.

## 1. Create a read-only MySQL user (once)

**Do not use `GRANT SELECT ON fade.*`.** This database also holds
`auth_user` (password hashes), `django_session` (live session keys),
`otp_static_staticdevice`/`otp_static_statictoken`/`otp_totp_totpdevice`
(2FA secrets -- leaking these would let someone compute valid login codes),
and `sensors_sensor.webdav_password`/`api_key` (sensor credentials). A
blanket grant hands the analyst all of it. Grant only the tables analysis
actually needs, and for `sensors_sensor` specifically, only the non-secret
columns:

```bash
docker compose exec db mysql -u root -p
```
```sql
CREATE USER 'analyst'@'%' IDENTIFIED BY '<pick a strong password>';

GRANT SELECT ON fade.captures_monitoringsession TO 'analyst'@'%';
GRANT SELECT ON fade.captures_rayhunterlogentry TO 'analyst'@'%';
GRANT SELECT ON fade.ingestion_ingestedfile TO 'analyst'@'%';
GRANT SELECT ON fade.radio_coveragepoint TO 'analyst'@'%';
GRANT SELECT ON fade.radio_radiocapture TO 'analyst'@'%';
GRANT SELECT ON fade.radio_radiopacket TO 'analyst'@'%';
GRANT SELECT ON fade.sensors_country TO 'analyst'@'%';
GRANT SELECT ON fade.sensors_sensortype TO 'analyst'@'%';
GRANT SELECT ON fade.telemetry_telemetryrecord TO 'analyst'@'%';
GRANT SELECT (id, name, slug, is_active, notes, created_at, updated_at, sensor_type_id, country_id)
  ON fade.sensors_sensor TO 'analyst'@'%';

FLUSH PRIVILEGES;
```
`'%'` is fine here because the user can only ever reach this account through
the loopback-bound port via an SSH tunnel -- it's never reachable as
`'analyst'@'<their-ip>'` directly from the internet.

**Verified** (2026-11-18, against a real MySQL 8 instance): reads against
the granted tables/columns succeed; `INSERT`/`DROP` are rejected;
`SELECT webdav_password FROM sensors_sensor` is rejected; `auth_user` and
all three `otp_*` tables are completely inaccessible (`SELECT command
denied ... for table`); the join query in the starter notebook below
returns correct data. If new tables with sensitive columns are added later
(e.g. a future case-management feature), add them to the exclusion list
above before granting anything broader.

## 2. Give the analyst a tunnel-only SSH key (once per analyst)

Generate a dedicated keypair for them (don't reuse an existing login):
```bash
ssh-keygen -t ed25519 -f analyst_key -C "analyst-db-access"
```
Add the **public** key to the server under a restricted entry in
`~/.ssh/authorized_keys` (for whichever Linux user you're comfortable
granting this to -- a dedicated low-privilege account is best, but isn't
required for the restriction itself to work):
```
command="echo 'This key only allows port forwarding.'",no-pty,no-agent-forwarding,no-X11-forwarding,no-user-rc,permitopen="127.0.0.1:3306" ssh-ed25519 AAAA... analyst-db-access
```
This key can open the tunnel below and *nothing else* -- no shell, no
`docker compose exec`, no other port. Send the analyst the **private** key
(`analyst_key`) and the MySQL password through separate channels.

## 3. From Google Colab

Colab runs on Google's own cloud VMs, not the analyst's laptop, so the
tunnel has to be opened programmatically in the notebook, not via a
terminal `ssh -L` command. Same security model either way -- MySQL is never
exposed publicly.

**`docs/analyst_starter_notebook.ipynb`** in this repo is a ready-to-use
notebook implementing exactly this -- credentials loaded from Colab's
Secrets panel (never pasted into a cell), the tunnel, the connection, and
two working example queries. Test it yourself before handing it to anyone:

1. Go to [colab.research.google.com](https://colab.research.google.com),
   sign in, then File → Upload notebook → pick
   `docs/analyst_starter_notebook.ipynb` from this repo.
2. Follow the notebook's own "Step 1" cell -- it walks through adding your
   SSH key and DB password to Colab's Secrets panel (the key icon in the
   left sidebar), including the "Notebook access" toggle that's easy to
   miss on a first try.
3. Fill in the `SERVER_HOST` / `SSH_USERNAME` config cell with your real
   server's details.
4. Runtime → Run all. If the connectivity-check cell prints `1`, you're
   through the tunnel and authenticated; the two example-query cells below
   it should return real data.

Once you've confirmed it works end to end, generate a **separate** SSH
keypair and DB password for the actual analyst (per step 2 above -- don't
reuse the one you tested with), and send them:
- the notebook file itself (or a link to it, e.g. shared via Google Drive)
- the analyst's own private key
- the analyst's own DB password
- `SERVER_HOST`/`SSH_USERNAME` to fill into the config cell (not secret,
  fine in the same message as the notebook)

Send the key and the password through separate channels (e.g. one in an
encrypted message, the other read aloud on a call) -- same principle as any
credential handoff, since anyone who intercepts only one of the two still
can't connect.

## Notes

- `radio_radiopacket` is tens of millions of rows -- this is exactly the
  table this whole setup exists for (the Django admin changelist is
  deliberately not the analysis tool for it; see `radio/admin.py`'s
  `list_select_related` comment). Point the analyst at `RadioCapture` first
  for anything aggregate (it carries a precomputed `packet_count`) before
  querying `RadioPacket` directly for anything beyond a narrowly filtered
  slice.
- If analyst query volume ever becomes heavy enough to risk impacting the
  live app (the same database handles production writes), the next step
  would be a MySQL read replica dedicated to analyst traffic -- not needed
  for occasional/light use, so not built preemptively.
- Revoke access by removing the `authorized_keys` line and/or
  `DROP USER 'analyst'@'%';` -- either alone is sufficient, both together is
  cleanest.
- If a future feature adds a new table with sensitive columns, it's
  invisible to the analyst by default (nothing is granted automatically) --
  only add it to the GRANT list in step 1 if analysis genuinely needs it,
  and re-check for secret columns first, the same way `sensors_sensor` was
  checked here.
