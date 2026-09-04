#!/usr/bin/env sh
set -eu

api_password="$(tr -d '\r\n' < /run/secrets/api_password)"
case "$api_password" in
    ""|*"'"*) echo "API password secret is invalid." >&2; exit 1 ;;
esac

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gemeente_api') THEN
        CREATE ROLE gemeente_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
END \$\$;
ALTER ROLE gemeente_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    PASSWORD '$api_password';
REVOKE ALL ON DATABASE "$POSTGRES_DB" FROM gemeente_api;
REVOKE ALL ON SCHEMA public FROM gemeente_api;
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO gemeente_api;
SQL
