#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  SELECT 'CREATE DATABASE rehketo' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'rehketo')\gexec
  SELECT 'CREATE DATABASE bifrost' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'bifrost')\gexec
EOSQL
