#!/usr/bin/env sh
set -eu

app_password="$(tr -d '\r\n' < /run/secrets/app_password)"

if [ -z "$app_password" ]; then
    echo "Application password secret is empty." >&2
    exit 1
fi

case "$app_password" in
    *"'"*)
        echo "Application password contains an unsupported quote character." >&2
        exit 1
        ;;
esac

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE gemeente_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    PASSWORD '$app_password';
CREATE ROLE gemeente_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

REVOKE ALL ON DATABASE "$POSTGRES_DB" FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO gemeente_app, gemeente_reader;
GRANT CREATE ON DATABASE "$POSTGRES_DB" TO gemeente_app;
GRANT USAGE, CREATE ON SCHEMA public TO gemeente_app;
SQL
