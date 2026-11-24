-- The table FB_CH writes into. One row per value and sample; the server makes the time stamp from ago_ms
-- (how old the value was when it was sent), so the controller's own clock is not used.
CREATE DATABASE IF NOT EXISTS plc;

CREATE TABLE IF NOT EXISTS plc.samples
(
    ts     DateTime64(3) DEFAULT now64(3) - toIntervalMillisecond(ago_ms),
    tag    LowCardinality(String),
    value  Float64,
    ago_ms UInt32
)
ENGINE = MergeTree
ORDER BY (tag, ts)
TTL toDateTime(ts) + INTERVAL 90 DAY;
