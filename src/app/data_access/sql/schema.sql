-- Vigil schema (BACKEND_TZ §10). The only schema authority: applied at start
-- when `crew` is missing. SQLAlchemy models mirror it and create nothing.

create table if not exists crew (
  id        smallint primary key,
  name      text not null,
  role      text not null,
  dev_id    integer unique not null,
  share     jsonb not null default '{"sleep": true, "checkin": true}'
);

create table if not exists agg_1m (
  crew_id    smallint not null references crew,
  ts         timestamptz not null,           -- start of the minute
  hr real, spo2 real, rr real, skin_t real, hrv real,
  co2_ppm real, press_hpa real, amb_t real, ppco2 real,
  act_mg real, sqi real, worn_frac real, valid_s smallint,
  ctx        smallint not null,              -- 0 off, 1 sleep, 2 rest, 3 active
  z_hr real, z_spo2 real, z_rr real, z_skin_t real,
  lo_hr real, hi_hr real, lo_spo2 real, hi_spo2 real,
  lo_rr real, hi_rr real, lo_skin_t real, hi_skin_t real,
  level      smallint not null default 0,
  learn_mask smallint not null default 0,
  primary key (crew_id, ts)
);

create table if not exists alert (
  id         bigserial primary key,
  crew_id    smallint not null references crew,
  key        text not null,                  -- 'incident' | 'checkin:2026-11-14' | 'baseline_learned'
  source     text not null,                  -- baseline | hard | env | pattern | system
  ts_start   timestamptz not null,
  ts_update  timestamptz not null,
  ts_end     timestamptz,
  level      smallint not null,
  peak_level smallint not null,
  pattern    text, p real, ctx smallint,
  primary_m  text,
  metrics    jsonb not null default '[]',
  text       jsonb,
  text_src   text,
  ack_ts     timestamptz
);
create index if not exists alert_crew_ts_idx on alert (crew_id, ts_start desc);

create table if not exists checkin (
  crew_id smallint not null references crew,
  day date not null,
  sleep_q smallint, mood smallint, energy smallint,
  symptoms text[] not null default '{}',
  note text, filed_ts timestamptz not null,
  primary key (crew_id, day)
);

create table if not exists report (
  crew_id smallint not null references crew,
  day date not null,
  body jsonb not null,
  include jsonb not null,
  note text,
  queued_ts timestamptz,
  primary key (crew_id, day)
);

create table if not exists radiation_daily (
  day date primary key,
  dose real not null, unit text not null, instrument text not null
);

insert into crew (id, name, role, dev_id) values
  (1, 'M. Lindqvist', 'Commander', 1),
  (2, 'T. Herrera', 'Flight Engineer', 2),
  (3, 'A. Tanabe', 'Flight Engineer', 3),
  (4, 'N. Dube', 'Medical Officer', 4),
  (5, 'J. Weber', 'Mission Specialist', 5),
  (6, 'P. Raman', 'Mission Specialist', 6),
  (7, 'D. Markov', 'Payload Specialist', 7)
on conflict (id) do nothing;
