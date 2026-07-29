# Hardened MT5 RPyC bridge

This image pins the upstream MT5/VNC image by OCI digest and installs the
hash-verified RPyC 6.0.2 wheel into the Windows Python environment used by the
Wine RPyC server. The exact-match startup patch also pins Linux
`mt5linux==0.1.9` and fails closed if either interpreter does not report the
expected bridge versions.

## Security boundary

RPyC Classic exposes remote Python execution by design. It has no application
authentication or TLS in this deployment and must **never** be published on a
public interface. Production exposes port 8001 only to the private container
network. The local compose binds it to loopback only. A firewall/private network
is mandatory; if cross-host access is ever required, place a mutually
authenticated TLS tunnel in front of it rather than publishing RPyC Classic.

## Local validation

```bash
export MT5_VNC_PASSWORD='local-only-value'
docker compose -f mt5/compose.local.yaml up -d --build
uv run --project api python mt5/smoke-rpyc.py
```

The smoke performs only `import`, version evaluation, and read-only
`mt5.terminal_info()`. It does not log in, place orders, or call
`mt5.shutdown()`.

## Production

Create and validate both dedicated networks and the persistent volume once on the
Dokploy host, before either deployment:

```bash
sudo ./mt5/ensure-production-network.sh
```

`trading-mt5-api` is an internal attachable overlay used only by the Swarm API
and MT5. `trading-mt5-egress` is a bridge used only by MT5 to reach broker
endpoints; never attach application services to it. RPyC remains unpublished on
the host. In Dokploy, attach exactly `trading-mt5-api` to the API application's
**Advanced > Networks** and redeploy the API. Set its MT5 host/port to
`mt5:8001`. Do not attach MT5 to `dokploy-network`, and do not attach the
dashboard, database, or any other service to either MT5 network. Keep VNC
loopback-bound and access it through an authenticated administrative tunnel.

The external networks and explicitly named volume `trading-mt5-config` survive
Compose/Dokploy redeploys. Never use `docker compose down -v`. Before migration,
preserve the exact prior deployment definition and data:

```bash
cd /etc/dokploy/compose/trading-platform-mt5docker-1uotpe/code
cp docker-compose.yml docker-compose.previous.yml
cp .env .env.previous
chmod 600 .env.previous
container_id="$(docker compose -p trading-platform-mt5docker-1uotpe \
  --env-file .env -f docker-compose.yml ps -q mt5)"
docker inspect "$container_id" --format '{{.Config.Image}} {{.Image}}' \
  > mt5.previous-image-id
docker run --rm -v trading-mt5-config:/config:ro -v "$PWD":/backup alpine:3.22 \
  tar czf /backup/mt5-config.pre-6.0.2.tgz -C /config .
```

## Persistent automated trading

MT5 starts with `/config:C:\mt5-autotrading.ini`. The configuration enables
automated trading and prevents account or profile changes from switching it
back off. Production stores this file in the persistent MT5 volume at
`/config/.wine/drive_c/mt5-autotrading.ini`; provision it from
`mt5/autotrading.ini` before starting or recreating the service. The local
Compose file mounts the tracked configuration directly.

Verify the setting without placing an order by reading `terminal_info()` through
the private RPyC bridge. Both `trade_allowed` and `connected` must be true, while
`tradeapi_disabled` must be false.

Promotion criteria: effective Compose config contains only
`trading-mt5-api` and `trading-mt5-egress`; only MT5 is attached to the egress
bridge; RPyC has no published host port; VNC is loopback-only; the container
uses `trading-platform/mt5-rpyc:6.0.2`; an API-side RPyC 6 smoke passes; and
credentialed `mt5.initialize`, `terminal_info`, and `account_info` succeed.

Roll back on any failed criterion with the preserved Compose definition:

```bash
cd /etc/dokploy/compose/trading-platform-mt5docker-1uotpe/code
docker compose -p trading-platform-mt5docker-1uotpe \
  --env-file .env.previous -f docker-compose.previous.yml \
  up -d --force-recreate --remove-orphans
```

Verify the recreated container image against `mt5.previous-image-id`. Restore
`mt5-config.pre-6.0.2.tgz` into a newly created recovery volume only if data
integrity validation fails; do not overwrite the last known-good volume and
never remove the dedicated networks during rollback.
