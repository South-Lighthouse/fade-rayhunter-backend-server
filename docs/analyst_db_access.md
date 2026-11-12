# Analyst access to the production database

Lets a data analyst query the production MySQL database directly (e.g. from
Google Colab) for offline analysis of radio packet data, without exposing
MySQL to the internet and without giving them a full server shell.

`db` in `docker-compose.yml` binds MySQL to `127.0.0.1:3306` on the host --
reachable only from the server itself, never from the internet, even if the
host firewall is misconfigured. The analyst reaches it through an SSH tunnel.

## 1. Create a read-only MySQL user (once)

```bash
docker compose exec db mysql -u root -p
```
```sql
CREATE USER 'analyst'@'%' IDENTIFIED BY '<pick a strong password>';
GRANT SELECT ON fade.* TO 'analyst'@'%';
FLUSH PRIVILEGES;
```
`'%'` is fine here because the user can only ever reach this account through
the loopback-bound port via an SSH tunnel -- it's never reachable as
`'analyst'@'<their-ip>'` directly from the internet.

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

```python
!pip install sshtunnel pymysql sqlalchemy -q

# Paste the private key into Colab's Secrets (key icon in the left sidebar),
# not directly in a cell -- keeps it out of the notebook's saved output.
from google.colab import userdata
import tempfile, os

key_path = tempfile.mktemp()
with open(key_path, "w") as f:
    f.write(userdata.get("ANALYST_SSH_KEY"))
os.chmod(key_path, 0o600)

from sshtunnel import SSHTunnelForwarder

tunnel = SSHTunnelForwarder(
    ("<server-ip-or-hostname>", 22),
    ssh_username="<the linux user the key is installed under>",
    ssh_pkey=key_path,
    remote_bind_address=("127.0.0.1", 3306),
)
tunnel.start()

from sqlalchemy import create_engine
import pandas as pd

engine = create_engine(
    f"mysql+pymysql://analyst:<password>@127.0.0.1:{tunnel.local_bind_port}/fade"
)
df = pd.read_sql("SELECT COUNT(*) FROM radio_radiopacket", engine)
df

# tunnel.stop() when done
```

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
