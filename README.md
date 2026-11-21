## Introduction to tecmap
"Transports en Commun" map is a lightweight map to locate bus in real-time using open data. On the map below, bus coordinates are refreshed every 30 seconds and are colored according to delay (by comparing real-time data to static theoretical timetables which can be displayed by clicking on one bus: red > 5 minutes, 0 < orange < 5 minutes, green on time). You can get timelines and other details when you click on a bus marker on the map.
![tecmap](tecmap-liege.jpg?raw=true "Tecmap in Liège, Belgium")

A simple filter (by bus line numbers) allows to only display the buses of interest (e.g. "21 58" will display buses following lines 21 and 58; "2?guill 58?guill" will display buses of line 2 that will pass through a stop which name includes "guill" as well as expected time schedule, and buses nr 58 that will pass through a stop name including "guill" which allow to organize your commute based on real-time data).
![tecmap](tecmap-filters.jpg?raw=true "Filter in Tecmap")

Alerts (disruptions) can be displayed for each line numbers to know about cancelled trips and stops.
![tecmap](tecmap-alerts.jpg?raw=true "Alerts in Tecmap")

The typical use cases include individuals wanting to know if their buses are on time to plan their trips, e.g. someone at home who doesn't want to wait 10 minutes outside in the cold, or someone who has the possibility of taking several different buses and wants to know which one will arrive first, or someone at their desk who wants to optimize their life and work until the last minute before their bus comes, or someone having a good time with a loved one but not wanting to miss the very last bus ;) or wanting to wait in a shady place rather than at the bus stop in direct sunlight. Another use case is someone who wants to discover new places they can reach with public transport without knowing the existing routes a priori. Please note no automatic planning is provided, you must use your mental calculation skills to construct your route, which in principle consumes less energy than running a routing algorithm on GAFAM servers. ;)

## Tech stack
tecmap has been developed using HTML, CSS and JavaScript without a web framework. Static routes, stops and schedules are generated locally from TEC GTFS data; vehicle positions, trip updates and service alerts come from Belgian Mobility's GTFS-Realtime API in protobuf format.


## TEC data from Belgian Mobility

The [Belgian Mobility data portal](https://data.belgianmobility.io) provides TEC/LETEC static GTFS and real-time feeds. The developer portal issues primary/secondary subscription keys; requests use the `bmc-partner-key` header.

Create a subscription key in the [developer portal](https://api-management-opendata-production.developer.azure-api.net/). Keep it on the server; never put it in `config.js` or browser code. Copy `server/.env.example` to `server/.env`, then set `BMC_PARTNER_KEY` to your primary or secondary key.

### Static routes, stops and schedules

The TEC GTFS zip is updated daily. From the repository root, run:

```sh
python3 -m pip install -r requirements.txt
python3 scripts/sync_gtfs.py
```

The script downloads `/api/gtfs/feed/tec/static`, validates and extracts the GTFS files, downloads the GTFS-Realtime protobuf schema, then runs the existing converters to refresh stops, routes, schedules and line geometries under `data/`. The large generated `data/` directory is local and is not committed to Git. Run this command daily on the host that serves the map to keep its static data current.

### Real-time positions, delays and alerts

The cache server fetches the TEC GTFS-Realtime feeds with the subscription key and exposes the JSON/Protobuf endpoints already used by the map:

| API feed | Upstream endpoint | Refresh |
|---|---|---:|
| Vehicle positions | `/api/gtfs/feed/tec/rt/vehicle-position?format=protobuf` | 30 seconds |
| Trip updates and delays | `/api/gtfs/feed/tec/rt/trip-update?format=protobuf` | 30 seconds |
| Service alerts | `/api/gtfs/feed/tec/rt/alert?format=protobuf` | 30 seconds |

The cache server sends the key in the `bmc-partner-key` header. The Standard tier allows 12,000 requests/day; polling these three feeds every 30 seconds uses about 8,640 requests/day.

Run the cache server from its directory so it loads `server/.env`:

```sh
cd server
npm install
npm start
```

The browser continues to call the cache server URLs configured in `config.js`; it never receives the Belgian Mobility key. Set `RT_VEHICLE_API_URL`, `RT_ALERT_API_URL`, and `RT_UPDATE_API_URL` there only if your cache server uses different public URLs.

## Run locally

Refresh static data with `python3 scripts/sync_gtfs.py`, then serve the repository root over HTTP and open `tecmap.html`. The app uses the locally generated `data/` assets and the real-time cache server.

Edit `TILE_API_KEY` in `config.js` if you want to use Thunderforest transport tiles. Otherwise, the default OpenStreetMap tile layer is used.

## Future plans, contact
I am aware of the limitations of such a client-side approach. 
Having a database to store routes and stops and an API called from the web client would be more elegant but for the moment I wanted to keep it very simple so that anyone can deploy it easily.
Please feel free to submit Issues or contact me.

## Acknowledgments
The map uses the open access [http://openstreetmap.org/](http://openstreetmap.org/) data and the open-source [https://leafletjs.com/](https://leafletjs.com/) Javascript library.
Transit data source: LETEC (TEC) via the [Belgian Mobility Open Data Portal](https://data.belgianmobility.io/), CC BY 4.0. Include the data update date in deployments when available.





