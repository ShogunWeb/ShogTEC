# Assistant guide

## Project overview

TECmap is a lightweight public-transit map for TEC in Belgium. The frontend is plain HTML, CSS, and JavaScript (no frontend framework). It combines locally generated static GTFS assets with live GTFS-Realtime data.

## Architecture and important files

- `tecmap.html`: map UI and most frontend logic.
- `config.js`: browser-side live API URLs, refresh interval, and optional tile API key. The frontend requests the live feeds from the cache server URLs defined here.
- `data/`: locally generated GTFS assets loaded by the browser. These assets may be absent from a fresh checkout and are not tracked in Git.
- `scripts/sync_gtfs.py`: downloads and validates the static TEC GTFS feed, then regenerates assets in `data/`.
- `convert_data.py` and `scripts/generate_line_shapes.py`: convert downloaded GTFS text files into browser-ready JavaScript assets.
- `server/server.js`: Express cache server. It fetches TEC GTFS-Realtime protobuf feeds from Belgian Mobility, decodes/transforms them, caches results in memory, and exposes endpoints for the browser.
- `service-worker.js`: caches the app shell and same-origin GET responses in the browser's Cache Storage.
- `server/.env.example`: example server configuration. `server/.env` is ignored by Git and must never be committed.
- `tests/test_sync_gtfs.py`: unit tests for GTFS archive extraction and validation.

Data flow:

1. The browser loads static stops, routes, schedules, and line shapes from local `data/` files.
2. The browser fetches real-time positions, alerts, and delays from the URLs in `config.js`.
3. The cache server fetches the upstream Belgian Mobility real-time feeds using the server-side subscription key; the browser must never receive that key.
4. Static GTFS data is downloaded and regenerated separately with `scripts/sync_gtfs.py`.

## Development commands

Run the Python tests from the repository root:

```sh
python3 -m unittest discover -s tests
```

Refresh static data (requires network access and a Belgian Mobility subscription key):

```sh
python3 -m pip install -r requirements.txt
python3 scripts/update_gtfs.py
```

To read the Belgian Mobility key from an env file outside the repository, copy `scripts/update_gtfs.config.example.json` to the ignored `scripts/update_gtfs.config.json` and set its `env_file` path. `--env-file /path/to/private/.env` can override it for one run.

Run the cache server from its directory so `loadEnvFile(".env")` can find the file:

```sh
cd server
npm install
npm start
```

The server README documents Node.js 24.13.1 as the tested version. The project has no root `package.json` or frontend build/test command.

## Configuration facts and caveats

- Put the subscription key in `server/.env` as `BMC_PARTNER_KEY` (legacy `API_KEY` is also accepted). Never copy a real key into source, logs, browser code, or documentation.
- `server/server.js` supports `BMC_API_BASE_URL` and `VERBOSE_LOGGING`; its upstream refresh intervals are currently fixed at 30 seconds in code.
- `PORT` is read before `loadEnvFile(".env")` runs. If a custom port is needed, supply it in the process environment; do not assume `PORT` in `server/.env` takes effect in the current implementation.
- `RT_VEHICLE_API_URL`, `RT_ALERT_API_URL`, `RT_UPDATE_API_URL`, and `RT_REFRESH_RATE` are browser settings defined in `config.js`; `server/server.js` does not read them from `.env`. Changing these names in the server env file does not redirect frontend requests.
- `server/.env.example` currently includes sample `RT_*` values for reference. Treat `config.js` as the source of truth for the browser URLs and refresh rate.
- The frontend expects the cache server endpoints `/api/vehicles`, `/api/alerts/raw`, and `/api/delays`. The server also exposes `/api/alerts`, `/`, and `/status`.
- `TILE_API_KEY` in `config.js` is optional; the README describes OpenStreetMap as the default map layer.
- The version line displays an approximate `navigator.storage.estimate()` usage for the site origin; if it reports zero, the UI falls back to summing available `Content-Length` headers for TECmap service-worker cache entries. Unknown entries are marked with `+`.
- Avoid running the live GTFS sync unless explicitly needed: it makes external requests and writes generated files under `data/`.

## Working practices

- Inspect the relevant code and current Git changes before editing; preserve unrelated local changes.
- Keep changes focused and follow existing plain-JavaScript/Python patterns.
- Do not add a framework or build system for the frontend without a requirement.
- Run the narrowest relevant test command after code changes. For documentation-only changes, tests are generally unnecessary.
- Generated assets and credentials are not source-code edits; do not commit generated `data/` files or `server/.env` unless the task explicitly requires a reviewed change to that policy.
