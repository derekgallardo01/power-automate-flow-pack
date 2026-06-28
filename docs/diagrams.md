# Diagrams

Beyond the inline ones in [architecture.md](architecture.md).

## 1. Decision tree — what happens to each row

```mermaid
flowchart TB
    R["Row pulled from source"] --> A{"Approved filter<br/>(only_approved)?"}
    A -- "no, filter on but row not approved" --> SK["Skipped — never enters the table"]
    A -- "yes / filter off" --> M["Map fields per mapping_config"]
    M --> P{"Row id in<br/>permanent_fail_ids?"}
    P -- "yes" --> DLQ["DLQ: written to dlq.json<br/>with reason + timestamp"]
    P -- "no" --> D{"Row id already<br/>in destination?"}
    D -- "yes" --> S2["Skipped — duplicate"]
    D -- "no" --> W{"Write succeeds?<br/>(retry up to 3x)"}
    W -- "yes" --> OK["Added to destination"]
    W -- "no, all retries failed" --> ABORT["Abort run<br/>(transient errors only)"]
```

## 2. Sequence — happy run with transient failure recovered

```mermaid
sequenceDiagram
    autonumber
    participant T as Scheduler
    participant F as run_sync
    participant Map as map_entries
    participant WR as with_retry
    participant WT as write_table

    T->>F: trigger (06:00 daily)
    F->>F: load source (5 entries) + mapping
    F->>Map: map_entries(entries, mapping)
    Map-->>F: 4 approved rows (1 unapproved skipped)
    F->>WR: with_retry(write_action, label="write")
    WR->>WT: attempt 1
    WT-->>WR: raise RuntimeError("transient timeout")
    WR->>WR: log "attempt 1 failed; retrying"
    WR->>WT: attempt 2
    WT-->>WR: {added: 4, total: 4, skipped: 0}
    WR->>WR: log "succeeded on attempt 2"
    WR-->>F: result
    F-->>T: log + {added:4, total:4, dlq_count:0}
```

## 3. Sequence — permanent failure routed to DLQ

```mermaid
sequenceDiagram
    autonumber
    participant T as Scheduler
    participant F as run_sync
    participant Map as map_entries
    participant WT as write_table
    participant DQ as write_dlq

    T->>F: trigger
    F->>F: load + map → 4 rows
    F->>F: permanent_fail_ids=["t1"] → split:<br/>3 good rows, 1 failed_row<br/>(with reason + ISO timestamp)
    F->>WT: write 3 good rows
    WT-->>F: {added: 3, total: 3, skipped: 0}
    F->>DQ: write_dlq([failed_row])
    DQ-->>F: dlq_count = 1
    F-->>T: log + {added:3, total:3, dlq_count:1}
    Note over F,T: Run completes successfully<br/>3 good rows landed; bad row in DLQ for human review
```

## 4. State — run lifecycle

```mermaid
stateDiagram-v2
    [*] --> Triggered: scheduled / manual / API
    Triggered --> Pulling: load source + mapping
    Pulling --> Mapping: list[dict] returned
    Mapping --> Splitting: apply approved filter
    Splitting --> Writing: send good_rows to write_action
    Splitting --> DLQ_Write: send failed_rows to write_dlq
    Writing --> Retrying: transient exception caught
    Retrying --> Writing: backoff + retry
    Writing --> DLQ_Write: success path
    Retrying --> Failed: exhausted attempts
    Writing --> Notifying: success
    DLQ_Write --> Notifying
    Notifying --> [*]: log + summary returned
    Failed --> [*]: propagate the error
```

## 5. Data flow — across source variants

```mermaid
flowchart LR
    subgraph Asana["Asana scenario"]
      A1["asana_export.json<br/>(approval-filtered)"]
      A2["mapping-config.json<br/>key=EntryId"]
    end
    subgraph Forms["Microsoft Forms scenario"]
      F1["forms-responses.json<br/>(no approval filter)"]
      F2["mapping-config-forms.json<br/>key=RequestId"]
    end

    A1 --> ME["map_entries()"]
    A2 --> ME
    F1 -.-> ME
    F2 -.-> ME

    ME --> WT["write_table()<br/>(idempotent upsert on mapping['key'])"]
    ME --> DLQ["write_dlq()<br/>(rows in permanent_fail_ids)"]
    WT --> OUT["excel_table.json"]
    DLQ --> DOUT["dlq.json"]
```
