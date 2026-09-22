# Notes for Rafael — globe.tsx

## TL;DR: the API contract has not changed

The backend was restructured into a proper Python package (`src/skylens/`), but
**every endpoint, field name and value is byte-identical**. Verified across all
58 airports and all 16 scorer fields. `GET /airports/scores` still returns the
same shape, still with `lat` / `lon` / `name` merged in.

Nothing in `frontend/` was touched, and you don't need to change anything for
your build to keep working. The items below are separate — things spotted while
reading the map, worth a look when you have time.

---

## 1. The score colour ramp is inverted (highest priority)

`getScoreColor` in `src/app/globe.tsx` currently maps:

| score | colour |
|---|---|
| 0 | dark red `rgb(110, 20, 20)` |
| 50 | amber `rgb(245, 158, 11)` |
| 100 | bright green `rgb(57, 255, 112)` |

But in the model, **a high score means high congestion**. The score is
`live_aircraft / (peak_capacity × weather_penalty) × 100`, and the cascade
simulation treats anything `>= 65` as a stressed airport that propagates delays
downstream.

So right now the map paints the *most congested* airports green and the
*quietest* ones red. On the last data snapshot, the green markers were DFW, OAK,
SAN and SJC — all at score 100.0, i.e. at or over peak capacity.

**Fix:** swap the two endpoint colours so red = high score = congested.

```ts
const getScoreColor = (score: number) => {
  const normalizedScore = Math.max(0, Math.min(score, 100)) / 100;

  // 0 = quiet -> green, 50 -> amber, 100 = congested -> red
  if (normalizedScore <= 0.5) {
    return interpolateColor([57, 255, 112], [245, 158, 11], normalizedScore * 2);
  }

  return interpolateColor(
    [245, 158, 11],
    [110, 20, 20],
    (normalizedScore - 0.5) * 2,
  );
};
```

A legend somewhere on the map would also help — right now there's no way for a
viewer to know what the colours mean.

---

## 2. "No data" airports look identical to quiet airports

OpenSky has weak receiver coverage over East Asia, so some airports come back
with zero state vectors. They score 0.0 and currently render as dark red,
exactly like an airport that genuinely has no traffic.

The API already tells you this — your `AirportInfo` interface even declares the
fields, they're just not read anywhere:

```ts
live_data_status: string;   // "ok" | "no_states" | "api_error" | "network_error"
live_data_message: string;  // human-readable explanation
```

On the last snapshot, 4 of 58 airports were `no_states` (YOW, NRT, KIX, PVG).

**Suggestion:** when `live_data_status !== "ok"`, render the marker in a neutral
grey with reduced opacity instead of a score colour, and surface
`live_data_message` in the callout. A grey pin reads as "unknown", which is the
truth, rather than "quiet", which isn't.

Related: of the 16 fields the API sends, the map currently uses 4 (`name`,
`lat`, `lon`, `score`). `weather_penalty`, `wind_kn`, `live_peak_count`,
`peak_source` and `model_trained` are all there if the callout ever wants more.

---

## 3. The launch viewport opens too tight

```ts
initialRegion={{
  latitude: 39.3017,
  longitude: -94.7139,   // Kansas City
  latitudeDelta: 10,
  longitudeDelta: 10,
}}
```

At that delta only **2 of 58** airports (MCI and STL) are in frame — everything
else needs a pinch-out, which is why your screenshot is zoomed way further than
the default. There are also 13 international airports (LHR, CDG, FRA, AMS, DXB,
SIN, ICN, SYD, HND, NRT, KIX, PVG, YYZ) being rendered off-screen every launch.

**Suggestion:** either widen the deltas so the continental US fits on first
paint, or `fitToCoordinates` over the returned airports once data lands so the
view always frames whatever the API actually sent.

---

## 4. Smaller things

- **Marker overlap.** The Northeast/Midwest cluster is unreadable at low zoom.
  `react-native-maps` supports marker clustering, or you could scale marker size
  with zoom level.
- **Stale-data indicator.** The refresh button re-fetches the cache, but the
  server only recomputes every 15 minutes, so a tap can return data up to 15 min
  old with no visual difference. Every airport carries a `timestamp` — showing
  "updated 4 min ago" would make the button honest. (A `POST /refresh` endpoint
  that forces a recompute is on the backend list, but it needs the upstream
  fetches parallelised first — a full sweep currently takes ~30s.)
- **Search and filter are still wired to nothing** — the `TextInput` has no
  `onChangeText` and the funnel button `console.log`s. Just flagging in case
  they read as "done" from the outside.

---

## New: forecast fields are now available (backwards compatible)

The API now runs the trained quantile models at request time and ships five new
fields. **Nothing you have breaks** — all 19 fields your `AirportInfo` interface
declares are still there, unchanged. These are additions:

```ts
projected_score: number;      // score extrapolated one hour forward
expected_arrivals: number;    // model's arrivals/15min for the current slot
forecast_next_hour: {         // p10/p50/p90 are null when forecast_source is "historical"
  p10: number | null;
  p50: number | null;
  p90: number | null;
};
demand_trend: "rising" | "falling" | "steady" | "unknown";
forecast_source: "model" | "historical";   // 43 airports model, 15 historical
```

Ideas, if you want them:

- **A trend arrow on the marker** — `demand_trend` is the cheapest possible win:
  an up/down chevron next to the plane icon.
- **`projected_score` in the callout** — "53 now, 61 expected within the hour"
  reads as a forecast rather than a snapshot, which is the point of the project.
- **The uncertainty band** — `forecast_next_hour.p10`–`p90` is a real confidence
  interval from quantile regression. A small range bar would show it off.

Note `forecast_source`: 15 airports (mostly international) have no trained model
and return `"historical"` with `p10`/`p90` as `null`. Guard for that before
rendering a band.


---

## Coming later (will need coordination)

- **Generated TypeScript types.** Once the API returns Pydantic response models,
  `AirportInfo` can be generated from the OpenAPI spec instead of hand-kept in
  sync. A renamed backend field currently becomes a silent `undefined` on your
  side rather than a build error.
- **A hosted API URL.** Right now `EXPO_PUBLIC_API_URL` has to point at a LAN
  address, so the app only works on the same wifi as a running dev server. Once
  the backend is containerised and deployed you'll get a stable `https://` URL
  that works anywhere, including on cellular.
