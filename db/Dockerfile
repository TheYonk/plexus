# Plexus demo database: pgvector/pgvector:pg17 with the pg_synapse extension
# baked in, so one Postgres hosts the agent runtime (pg_synapse), the
# retrieval layer (pg-raggraph: pgvector + pg_trgm), the memory layer (stele
# artifacts + memories), and the ingest sink (chunkshop).
#
# The pg-synapse checkout comes in as the named build context "synapse"
# (docker-compose.yml). By hand, from this repo:
#   docker build --build-context synapse=../pg-synapse -t plexus-db db
#
# Stage 1 mirrors pg-synapse/demo/db/Dockerfile: build the pgrx extension
# against PGDG postgresql-server-dev-17 so install paths line up with the
# official postgres:17 image that pgvector/pgvector:pg17 is derived from.

FROM rust:1-bookworm AS builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      postgresql-common ca-certificates gnupg clang libclang-dev pkg-config \
 && YES=1 /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-server-dev-17 \
 && rm -rf /var/lib/apt/lists/*

RUN cargo install --locked cargo-pgrx --version 0.18.0
RUN cargo pgrx init --pg17 /usr/lib/postgresql/17/bin/pg_config

WORKDIR /src
COPY --from=synapse . .

RUN cd crates/pg-synapse-pgrx \
 && cargo pgrx package --no-default-features \
      --features "pg17 tools-http tools-calc tools-clock tools-delegate tools-fs"

FROM pgvector/pgvector:pg17

COPY --from=builder /src/target/release/pg_synapse_pgrx-pg17/ /
COPY --from=builder /src/crates/pg-synapse-pgrx/sql/ /opt/pg-synapse-sql/
