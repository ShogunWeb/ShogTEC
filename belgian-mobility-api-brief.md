# Belgian Mobility API — TEC/LETEC

## Portals and authentication

- Data catalog: https://data.belgianmobility.io/en/data.html?agency=tec
- Developer portal: https://api-management-opendata-production.developer.azure-api.net/
- API gateway used by the examples: `https://api-management-discovery-production.azure-api.net`
- Authentication header: `bmc-partner-key: <subscription key>`
- Keep the primary or secondary key in `server/.env` as `BMC_PARTNER_KEY`; never expose it in browser code.

The public catalog states that static GTFS is updated daily and GTFS-Realtime feeds approximately every 30 seconds. Standard registered access is listed as 12,000 requests/day and 500 requests/minute. Public reuse requires CC BY 4.0 attribution.

## TEC endpoints used by ShogTEC

| Endpoint | Format | Purpose | Refresh |
|---|---|---|---|
| `/api/gtfs/feed/tec/static` | ZIP GTFS | Routes, stops, trips, stop times, calendars and shapes | Daily |
| `/api/gtfs/feed/tec/rt/vehicle-position?format=protobuf` | GTFS-Realtime protobuf | Live vehicle positions | ~30 seconds |
| `/api/gtfs/feed/tec/rt/trip-update?format=protobuf` | GTFS-Realtime protobuf | Trip delays and updates | ~30 seconds |
| `/api/gtfs/feed/tec/rt/alert?format=protobuf` | GTFS-Realtime protobuf | Service alerts | ~30 seconds |

Example:

```sh
curl \
  -H "bmc-partner-key: $BMC_PARTNER_KEY" \
  -o gtfs-tec.zip \
  "https://api-management-discovery-production.azure-api.net/api/gtfs/feed/tec/static"
```

ShogTEC's backend proxy decodes the protobuf feeds and returns the formats already consumed by the map. The static GTFS sync script downloads the ZIP and regenerates the local stop, route, schedule and line-shape assets.

## Notes

- The API documentation also describes direct GTFS-RT protobuf endpoints and SIRI feeds; ShogTEC currently uses the unified `/api/gtfs/feed/tec/...` routes.
- The portal's terms require attribution such as `Source: LETEC (TEC) – Belgian Mobility Open Data – <update date>`.
