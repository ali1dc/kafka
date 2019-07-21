#!/bin/bash

export PGHOST=$(keystore.rb retrieve --table $keystore_table --keyname KAFKA_CONSUMER_RDS_HOST)
export PGPORT=5432
export PGDATABASE=postgres
export PGUSER=$(keystore.rb retrieve --table $keystore_table --keyname KAFKA_CONSUMER_RDS_USER)
export PGPASSWORD=$(keystore.rb retrieve --table $keystore_table --keyname KAFKA_CONSUMER_RDS_PASSWORD)
debezium_host=$1

echo "pause the connector"
curl -X PUT http://${debezium_host}:8083/connectors/debezium-connector/pause

echo "drop the connections"
psql -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = 'postgres' AND pid <> pg_backend_pid();"

echo "deleting repliction slot for debezium"
psql -c "select pg_drop_replication_slot('debezium');"

echo "starting the debezium connector"
curl -X PUT http://${debezium_host}:8083/connectors/debezium-connector/resume
curl -X POST http://${debezium_host}:8083/connectors/debezium-connector/tasks/0/restart

curl http://${debezium_host}:8083/connectors/debezium-connector/status | jq

psql -c "select slot_name, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(),restart_lsn)) as replicationSlotLag,active from pg_replication_slots;"

echo "*** done ***"
