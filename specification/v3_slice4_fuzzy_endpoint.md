# 🧩 Slice Execution Spec: Fuzzy Data Overlay API + UI Prep (Slice 4)

## 🎯 Goal

Expose fuzzy membership values from the backend for each indicator over time, allowing the frontend to render fuzzy overlays on charts. This slice does not include the rendering — only API + UI wiring to receive and inspect the data.

---

## 🧩 Background

The fuzzy engine computes membership scores for each configured fuzzy set per indicator (e.g. low/neutral/high for RSI). While the backend can already preview a single fuzzy value (`GET /fuzzy/preview`), there is no API to return fuzzy membership data across time.

The frontend requires a batch endpoint to retrieve fuzzy overlays for each indicator over a given OHLCV window.

---

## 📦 Inputs

| Source          | Data                                     |
| --------------- | ---------------------------------------- |
| UI/API Call     | `symbol`, `timeframe`, `indicators[]`    |
| Backend Cache   | Existing OHLCV data                      |
| Strategy Config | Fuzzy sets defined per indicator in YAML |

---

## 🔁 Logic & Flow

### 🔍 Validation & Behavior

* `symbol` and `timeframe` are **required** query parameters (string).
* `indicators[]` is **optional**:

  * If omitted, return all indicators that are both available and fuzzy-configured.
  * If provided, validate each name:

    * If the indicator is unknown → **skip and log a warning**
    * If known but missing fuzzy config → **skip and log**
* ⚠️ The endpoint supports **partial results**:

  * Indicators that are invalid or unfuzzy-configured will be excluded from the result
  * An optional `warnings[]` field may be included in the response
* Consistent default OHLCV range logic reused from `/data` and `/indicators/calculate`
* Light logging:

  * Symbol, timeframe, indicator list
  * Number of bars processed
  * Number of skipped indicators due to missing fuzzy config

1. **Receive Request**

   * Endpoint: `GET /fuzzy/data`
   * Params: `symbol`, `timeframe`, optional `indicators` list (if not supplied, return all configured)

2. **Load OHLCV Data**

   * Load historical OHLCV data using `DataManager`
   * Slice to default range (e.g. most recent 10000 bars) or add `start`/`end` support if needed

3. **Apply Indicators**

   * Use `IndicatorEngine` to compute indicator values for relevant columns

4. **Compute Fuzzy Memberships**

   * For each indicator + timestamp, compute fuzzy set memberships using `FuzzyEngine`
   * Return result as array of `[timestamp, set_name, value]`

5. **Group and Respond**

   * Structure response for frontend-friendly rendering:

```json
{
  "symbol": "AAPL",
  "timeframe": "1h",
  "data": {
    "rsi": [
      {
        "set": "low",
        "membership": [ { "timestamp": "...", "value": 0.8 }, ... ]
      },
      {
        "set": "neutral",
        "membership": [ { "timestamp": "...", "value": 0.1 }, ... ]
      }
    ]
  }
}
```

---

## 🧪 Tests (Definition of Done)

| Test                      | Condition                                          |
| ------------------------- | -------------------------------------------------- |
| Fuzzy API response shape  | `GET /fuzzy/data` returns valid structure per spec |
| Indicator + fuzzy linkage | Fuzzy sets match configured YAML indicator names   |
| Time alignment            | Membership points match OHLCV timestamps           |
| No hardcoded indicators   | Returns based on config, not code-level enum       |

---

## 🛡 Affected Modules

| Module                        | Description                                         |
| ----------------------------- | --------------------------------------------------- |
| `fuzzy/engine.py`             | Add batch fuzzy membership evaluation               |
| `api/endpoints/fuzzy.py`      | New `GET /fuzzy/data` endpoint                      |
| `api/models/fuzzy.py`         | New response model                                  |
| `services/fuzzy_service.py`   | Internal logic for fuzzy set aggregation            |
| `frontend/src/api/fuzzy.ts`   | Typed client for `GET /fuzzy/data`                  |
| `frontend/hooks/useFuzzyData` | Hook to call and store fuzzy overlay data           |
| `frontend/store/`             | Add fuzzy overlay state scaffold (no rendering yet) |

---

## 🧩 TypeScript Interface – Fuzzy Overlay Response

```ts
export interface FuzzyMembershipPoint {
  timestamp: string;
  value: number;
}

export interface FuzzySetMembership {
  set: string;
  membership: FuzzyMembershipPoint[];
}

export interface FuzzyOverlayData {
  [indicator: string]: FuzzySetMembership[];
}

export interface FuzzyOverlayResponse {
  symbol: string;
  timeframe: string;
  data: FuzzyOverlayData;
  warnings?: string[];
}
```

---

## 🧩 Frontend Hook – `useFuzzyData`

```ts
export function useFuzzyData(symbol: string, timeframe: string, indicators?: string[]) {
  const [data, setData] = useState<FuzzyOverlayData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = async () => {
    setLoading(true);
    try {
      const response = await getFuzzyOverlay(symbol, timeframe, indicators);
      setData(response.data);
      if (response.warnings) console.warn(response.warnings);
    } catch (err) {
      setError("Failed to load fuzzy data");
    } finally {
      setLoading(false);
    }
  };

  return { data, loading, error, fetch };
}
```

---

## 🧩 Store Strategy

* Store structure:

```ts
interface AppState {
  fuzzyOverlays: FuzzyOverlayData | null;
}
```

* Extend global reducer with actions:

  * `SET_FUZZY_OVERLAYS`
  * `CLEAR_FUZZY_OVERLAYS`
* Use selector hooks like `useFuzzyOverlay(symbol, tf)` to pull scoped overlays

---

## 🔄 Follow-up Slices

* **Slice 4.5**: Rendering fuzzy overlays on charts (transparency, color bands)
* **Slice 5**: Dynamic fuzzy config UI (read from YAML, allow param tweaking)
