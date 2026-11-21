# Accès aux données TEC (Wallonie) via MobilityTwin.Brussels

## Site / plateforme
- **URL principale** : https://mobilitytwin.brussels/
- **Documentation API** : lien "View API Documentation" sur https://mobilitytwin.brussels/tag/TEC/
- **Auth** : compte gratuit (email, pas de CB requise) → génération d'un token **Bearer** dans le compte utilisateur
- **Pas de limite d'usage** pour un usage de recherche/perso
- Support MCP disponible : possibilité de connecter directement un agent IA à l'API sans code

## Endpoints TEC disponibles (7 au total)

| Endpoint | Format | Contenu | Fréquence | Historique |
|---|---|---|---|---|
| `/tec/gtfs` | ZIP GTFS standard | stops.txt, routes.txt, trips.txt, stop_times.txt, calendar.txt | Quotidien | depuis 2024-08-21 |
| `/tec/gtfs-parquet` | ZIP de fichiers .parquet (zstd) | Même contenu que gtfs, 40-75% plus léger | Quotidien | depuis 2024-08-21 |
| `/tec/gtfs-realtime` | Binaire GTFS-RT (octet-stream) | Flux GTFS-RT brut complet | 20 secondes | depuis 2024-08-21 |
| `/tec/gtfs-rt-vehicle-positions` | GTFS-RT | Positions GPS des véhicules | 20 secondes | depuis 2024-08-21 |
| `/tec/gtfs-rt-trip-update` | GTFS-RT | Retards, avances, annulations par trajet | 20 secondes | depuis 2026-03-30 |
| `/tec/gtfs-rt-alert` | GTFS-RT | Alertes de perturbation | 15 minutes | depuis 2026-03-30 |
| `/tec/punctuality` | Fichier Parquet unique | Table de ponctualité quotidienne dérivée du trip-update | Quotidien | depuis 2024-08-22 |

**Note technique** : les `trip_id` / `route_id` / `stop_id` du GTFS statique correspondent directement à ceux des flux GTFS-RT.

**Sécurité** : l'API nécessite un header `Authorization: Bearer <token>`. Pour une app mobile/browser publique, ne pas exposer le token côté client — utiliser un petit proxy serveur qui masque la clé.

## Librairies recommandées

### Python (backend / scripts)
- `requests` ou `httpx` — appels HTTP avec Bearer token
- `gtfs-realtime-bindings` — décodage protobuf officiel (Node/Python only, pas pour browser)
- `polars` ou `duckdb` — lecture des fichiers Parquet
- `pandas` — manipulation de données décodées
- `zipfile` (stdlib) — extraction des archives GTFS

### JavaScript / Node.js (backend)
- `axios` ou `fetch` natif
- `gtfs-realtime-bindings` (npm) — décodage protobuf, conçu pour Node.js
- `duckdb` (npm) — lecture Parquet côté serveur
- `adm-zip` / `jszip` — extraction ZIP GTFS

### JavaScript — compatible navigateur / smartphone (PWA, app mobile web)
`gtfs-realtime-bindings` officiel n'est PAS conçu pour tourner nativement dans un navigateur (dépendance Node). Utiliser à la place :

- **protobuf.js** (recommandé) — supporte nativement l'encodage/décodage vers `Uint8Array` en environnement navigateur. Charger le schéma `gtfs-realtime.proto`, puis `FeedMessage.decode(buffer)` sur la réponse d'un `fetch()`. Solution la plus flexible et maintenue.
- **pbf + gtfs-realtime-pbf-js-module** — alternative légère, prête à l'emploi via CDN (`unpkg.com/pbf`, `unpkg.com/gtfs-realtime-pbf-js-module`), sans étape npm : `fetch()` → `ArrayBuffer` → `new Pbf(...)` → `FeedMessage.read(pbf)`.
- Référence de code : visualiseur GTFS 100% client-side (HTML/JS pur, sans serveur) combinant GTFS statique + GTFS-RT avec auto-refresh 15s et carte, basé sur protobuf.js (gist croyla/50ebbcd83ac4bce021c3070a18dbb9c2).

## Flux de travail typique (app mobile)
1. Backend/proxy léger détient le Bearer token MobilityTwin, sert de relai vers `/tec/gtfs-rt-vehicle-positions` (évite d'exposer le token au client).
2. App mobile (PWA) fait un `fetch()` vers ce proxy toutes les ~20s.
3. Décodage protobuf côté client avec `protobuf.js`.
4. Jointure avec un GTFS statique local (`/tec/gtfs-parquet`, mis en cache) pour afficher ligne/direction/arrêt.
5. Affichage carte (Leaflet, MapLibre) des positions décodées.

## Comparaison rapide avec transportdata.be
transportdata.be (NAP belge) ne référence pour le TEC qu'un GTFS statique — aucun flux GTFS-RT n'y est listé. MobilityTwin.Brussels est la seule des deux plateformes à exposer des endpoints RT documentés et utilisables pour le TEC.
