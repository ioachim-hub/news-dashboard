# Keycloak authentication

`news-dashboard` can use the existing minipc Keycloak instance as the public login provider while keeping the app's local `users` table as the per-user authorization/data boundary.

## Runtime flow

1. The frontend calls `GET /api/auth/config`.
2. When `KEYCLOAK_AUTH_ENABLED=1`, the login screen shows the new dashboard-style `Sign in with Keycloak` button.
3. `/auth/login` redirects the browser to Keycloak using Authorization Code flow.
4. `/auth/callback` exchanges the code, reads Keycloak `userinfo`, creates or reuses a local app user, and sets the existing signed `nd_session` cookie.
5. All existing authenticated API routes continue to use `require_auth`, so article state, source subscriptions, briefings, and admin routes remain scoped by local `user_id`.

Keycloak-created users receive an unusable random local password because Keycloak owns authentication. The comma-separated `KEYCLOAK_ADMIN_USERNAMES` env var controls which Keycloak usernames become app admins on first login; the local default is `ioachim`.

## Backend environment

Required when Keycloak auth is enabled:

```bash
KEYCLOAK_AUTH_ENABLED=1
NEWS_DASHBOARD_BASE_URL=https://news.lihor.ro
KEYCLOAK_SERVER_URL=https://news.lihor.ro/keycloak
KEYCLOAK_INTERNAL_SERVER_URL=https://news.lihor.ro/keycloak
KEYCLOAK_REALM=news-dashboard
KEYCLOAK_CLIENT_ID=news-dashboard
KEYCLOAK_ADMIN_USERNAMES=ioachim
SESSION_SECRET=<long random string>
```

`KEYCLOAK_SERVER_URL` is the browser-visible issuer base. `KEYCLOAK_INTERNAL_SERVER_URL` may point to an internal service if one exists; for the minipc same-host reverse proxy it intentionally matches the public URL.

## Caddy

`deploy/news.lihor.ro.caddyfile` exposes Keycloak under the same hostname:

```caddy
handle /keycloak* {
	reverse_proxy 127.0.0.1:8081
}
```

This avoids a separate DNS record and keeps redirect URIs under `https://news.lihor.ro`.

## Helm

The chart exposes the Keycloak settings under `app.auth` in `helm/news-dashboard/values.yaml`. When `app.auth.enabled=true`, Helm renders an auth Secret containing `SESSION_SECRET` and injects the Keycloak env vars into the app deployment.

For local deployment, override `app.auth.sessionSecret` with a generated value:

```bash
helm upgrade --install news-dashboard ./helm/news-dashboard \
  --set app.auth.sessionSecret="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

## Keycloak realm/client

Recommended realm/client values:

- Realm: `news-dashboard`
- Client ID: `news-dashboard`
- Client type: public OpenID Connect client
- Valid redirect URI: `https://news.lihor.ro/auth/callback`
- Valid post-logout redirect URI: `https://news.lihor.ro`
- Web origin: `https://news.lihor.ro`

## Login theme

The custom Keycloak theme lives in:

```text
deploy/keycloak-theme/news-dashboard/login/
```

It extends `keycloak.v2` and overrides only CSS. The CSS mirrors the new Radar Dashboard app shell: `RD` mark, compact centered card, warm OKLCH background/card colors, rounded inputs, dark foreground button, and dark-mode support.

Mount it into the Keycloak container at:

```text
/opt/keycloak/themes/news-dashboard
```

Then set the realm login theme to `news-dashboard`.

For local development/self-hosting, disable Keycloak theme caching while iterating:

```yaml
KC_SPI_THEME_CACHE_THEMES: "false"
KC_SPI_THEME_CACHE_TEMPLATES: "false"
KC_SPI_THEME_STATIC_MAX_AGE: "-1"
```
