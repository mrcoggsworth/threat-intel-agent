

## Analyst API

The Hermes analyst profile uses `https://matrix-1.taild27e3c.ts.net:9443` for
`/api/v1/analyst/*`. Host Nginx forwards this Tailscale-allowlisted surface to
the loopback-only web port `127.0.0.1:18000`; application authorization still
requires the analyst service token.
