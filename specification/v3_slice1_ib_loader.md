# 🯩 Slice Execution Spec: IB Loader (Slice 1)

## 🌟 Goal

Enable fetching OHLCV historical data from Interactive Brokers to fill *either* recent gaps (*tail fill*) or older periods (*backfill*), writing clean, chronologically ordered CSVs. Respect IB pacing rules. Triggerable via CLI, API, and (eventually) UI.

---

## 🯩 Background

Currently, all OHLCV data comes from static CSV files. There’s no integration with Interactive Brokers. This slice introduces programmatic fetching, while treating local CSVs as a persistent cache to avoid redundant queries.

---

## 📦 Inputs

| Source         | Data                                                        |                                   |
| -------------- | ----------------------------------------------------------- | --------------------------------- |
| CLI / API / UI | `symbol`, `timeframe`, \`mode: 'tail'                       | 'backfill'\`, optional date range |
| CSV            | Last known bar (tail fill) OR earliest known bar (backfill) |                                   |
| Config         | IB credentials (host/port), allowed timeframes              |                                   |

**IB Credential Defaults:**

* `host`: defaults to `localhost`
* `port`: defaults to 4001 (paper) or 7496 (live), overridable via config or CLI

*Note: IB rate limits are defined by IB specifications and are not configurable.*

---

## ♻️ Logic & Flow

### 1. **Mode Decision**

* **CSV not found**:

  * If no local CSV exists for a given `symbol` + `timeframe`, treat all modes (`tail`, `backfill`) as a **full initialization**.
  * `start_date` will default to the widest allowed historical range (based on IB limits for the selected timeframe).
  * `end_date = now()` unless overridden by API input.

* **Tail**:

  * Get latest timestamp in local CSV.
  * `start_date = latest_bar + 1 bar`
  * `end_date = now()` or API-supplied override.

* **Backfill**:

  * Get earliest known timestamp in CSV.
  * `start_date = earliest_bar - N bars`, where `N` is based on IB's maximum allowed request size for the selected timeframe (e.g., \~1 year for daily data). This default is determined per timeframe and is API-overridable.
  * `end_date = earliest_bar - 1 bar`

### 2. **IB Fetch Constraints**

#### ✅ Official Historical Data Request Limits

| Bar Size | Maximum Duration per Request |
| -------- | ---------------------------- |
| 1 sec    | 30 minutes                   |
| 5 secs   | 2 hours                      |
| 15 secs  | 4 hours                      |
| 30 secs  | 8 hours                      |
| 1 min    | 1 day                        |
| 5 mins   | 1 week                       |
| 15 mins  | 2 weeks                      |
| 30 mins  | 1 month                      |
| 1 hour   | 1 month                      |
| 1 day    | 1 year                       |
| 1 week   | 2 years                      |
| 1 month  | 1 year                       |

#### 🚦 Pacing Limits (Per IB)

To avoid pacing violations, adhere to the following restrictions:

* **No more than 60 historical data requests within any 10-minute period.**
* **Avoid making identical historical data requests within 15 seconds.**
* **Do not make six or more historical data requests for the same Contract, Exchange, and Tick Type within two seconds.**
* **When requesting BID\_ASK historical data, each request is counted twice.**

Violating these limits may result in pacing violations, leading to delayed responses or disconnections.

#### Retry & Backoff Strategy

#### Retry & Backoff Strategy

* **Retry Attempts:** Maximum 3 retries per failed chunk
* **Backoff Policy:** Exponential backoff: wait 2s, 4s, 8s after successive failures
* **Jitter:** Add ±20% randomness to backoff times to avoid clustering
* **Failure Logging:** All retries logged to `ib_fetch.log` with error and wait time
* **Abort Condition:** If all retries fail, raise detailed exception and halt process
* **Timeouts:** Per-request timeout (e.g., 15s) — cancel and retry on timeout
* Respect official IB maximum duration per request based on bar size:

  * `1 sec`: 30 minutes
  * `5 secs`: 2 hours
  * `15 secs`: 4 hours
  * `30 secs`: 8 hours
  * `1 min`: 1 day
  * `5 mins`: 1 week
  * `15 mins`: 2 weeks
  * `30 mins`: 1 month
  * `1 hour`: 1 month
  * `1 day`: 1 year
  * `1 week`: 2 years
  * `1 month`: 1 year
* Chunk accordingly.
* Respect pacing (sleep between requests).
* Retry up to 3x per chunk.

### 3. **Post-Fetch Handling**

* Fetched data is added to the CSV, ensuring it is sorted chronologically and deduplicated.
* Sort chronologically, de-dupe.
* Log all fetches to `ib_fetch.log`

---

## 🧪 Tests (Definition of Done)

| Test           | Condition                                                  |
| -------------- | ---------------------------------------------------------- |
| CLI Load       | `load_ib.py --symbol AAPL --tf 1h --mode tail` updates CSV |
| Backfill Load  | Loads older data and merges cleanly                        |
| Chunking       | Long ranges split and merged with no loss                  |
| Retry          | Failures retried with logging                              |
| API Call       | `POST /data/load` triggers correct IB logic                |
| CSV Validation | Resulting CSV is clean, ordered, deduped                   |

---

## 🛡 Affected Modules

*💡 Note: Current symbol selector only includes locally cached symbols (CSV-backed). To support loading new symbols from IB, we will introduce this functionality in a follow-up slice (Slice 1.5).*

| Module                        | Description                                      |
| ----------------------------- | ------------------------------------------------ |
| `IBDataLoader`                | Handles chunking, pacing, fetch logic            |
| `DataManager`                 | Delegates to `IBDataLoader` when CSVs incomplete |
| `cli/load_ib.py`              | CLI tool to trigger tail/backfill loads          |
| `api/data.py`                 | New `POST /data/load` endpoint                   |
| `frontend/src/api/data.ts`    | Hook to call load API                            |
| `frontend/src/components/...` | Panel or modal to trigger symbol/timeframe loads |

---

## 🧩 UI Design Proposal

## 📤 API Payload Format

**Endpoint**: `POST /data/load`

**Payload Example**:

```json
{
  "symbol": "MSFT",
  "timeframe": "1h",
  "mode": "tail",          // or "backfill"
  "start": "2023-01-01T00:00:00Z",  // optional override
  "end": "2024-01-01T00:00:00Z"      // optional override
}
```

**Validation Rules**:

* `symbol` and `timeframe` are required
* `mode` defaults to `tail` if missing
* `start` and `end` are optional but must match ISO 8601 format if provided
* `start` must be before `end`

**Response**:

```json
{
  "status": "success",
  "fetched_bars": 2432,
  "cached_before": true,
  "merged_file": "data/MSFT_1h.csv"
}
```

Errors return standard error format with HTTP 400 or 500 status codes.

### 🧱 Placement

* Group `Symbol` and `Timeframe` into a single form element at the top-left (currently separated).
* Add a **Load Data** section immediately below, scoped to current symbol + timeframe.

### 📐 Load Data Controls

| Control    | Type                | Description                                                    |
| ---------- | ------------------- | -------------------------------------------------------------- |
| Mode       | Dropdown            | `tail` (default), `backfill`                                   |
| Date Range | Optional DatePicker | User override (if desired)                                     |
| Trigger    | Button              | `Load from IB` — calls `POST /data/load` with selected context |

* Use selected `symbol` and `timeframe` from current dropdowns by default
* Display toast/success message on load completion

### 🔄 Follow-up Slice (1.5)

* New symbol support: expose searchable input and allow loading uncached symbols from IB

---

## 🚦 Decisions Needed

| Decision                                | Status                  |
| --------------------------------------- | ----------------------- |
| IB pacing constants per TF              | 🔲 Need from docs       |
| Error handling/backoff strategy         | 🔲 Decide retry policy  |
| UI method: dropdown, modal, in-context? | 🔲 Pick design pattern  |
| Configurable backfill window            | 🔲 Expose in config/API |
