# Cloud in a Bottle Garmin Health Producer

This repo contains a Cloud in a Bottle health data producer for Garmin Connect
devices (currently only smartwatches).

Garmin's official API is gated behind a developer portal, so data is sourced with
[GarminDB](https://github.com/tcgoetz/GarminDB), which logs into Garmin Connect,
downloads JSON + FIT files, and imports them into local SQLite databases.

## Linking your Garmin account — please read

**This app handles your real Garmin Connect password.** Garmin offers no
consent-based OAuth flow outside its developer portal, so linking works by
replaying your password against Garmin's own sign-in form once, exactly as the
Garmin Connect website does. There is no way around this short of Garmin granting
developer-portal access.

What that means in practice:

- The password is used for that one sign-in request and is **never written to
  disk** — not even to `GarminConnectConfig.json`, whose password field stays
  empty. Only the resulting OAuth token (`garmin_tokens.json`) is persisted.
- `/setup` is reachable only by the owner of the bottle, both through the
  router's owner gate and an in-app `X-OpenHost-Is-Owner` check.
- Credentials never leave the app; the only host contacted is Garmin's.
- If your account has MFA, you are prompted once. The token is what survives
  restarts, so you should not be asked again.

Unlinking from `/setup` deletes the saved token. Your downloaded health data is
kept.

## Status

Landed: the Garmin authentication flow and the container/manifest for deployment.

Not built yet: the background sync engine and the `/v1/*` service surface, so no
health data is served to consumers yet. See `plan.md` for the design of record
and `AGENTS.md` for the working agreement.

## Roadmap

Top priority is health data: heart rate, sleep cycles, body battery. Activity
export is planned in the indefinite future.
