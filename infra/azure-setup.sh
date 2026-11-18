#!/usr/bin/env bash
# One-time Azure setup for the flashcards system. Run once, by hand, from the repo root, after `az login`
# with the IE account. After this script the pipeline does every deployment; nothing is changed by hand.
#
# It creates, in the class resource group, everything with the prefix dpotec-ieu2024-:
#   1 SQL logical server with 2 serverless databases, 1 Static Web App,
#   1 Container Apps environment and 2 Container Apps.
# Every step checks whether the resource exists first, so the script can be run again after a failure.
#
# The three passwords come from environment variables of the shell that runs the script.
# They are never written to a file. Use letters and digits only: they end up inside a URL.
#   export SQL_ADMIN_PASSWORD=...  CONTENT_DB_PASSWORD=...  SCHEDULING_DB_PASSWORD=...
set -euo pipefail

PREFIX=dpotec-ieu2024
RG=rg-sdd-3b
SQL_SERVER=$PREFIX-sql
SQL_HOST=$SQL_SERVER.database.windows.net
SQL_ADMIN=sqladmin
ENVIRONMENT=$PREFIX-env
SWA=$PREFIX-ui
SWA_LOCATION=westeurope          # Static Web Apps exist only in a few regions
AUTO_PAUSE_MINUTES=15            # the shortest delay Azure allows; if Azure rejects it, use 60
PLACEHOLDER_IMAGE=mcr.microsoft.com/k8se/quickstart:latest

: "${SQL_ADMIN_PASSWORD:?set SQL_ADMIN_PASSWORD}"
: "${CONTENT_DB_PASSWORD:?set CONTENT_DB_PASSWORD}"
: "${SCHEDULING_DB_PASSWORD:?set SCHEDULING_DB_PASSWORD}"

LOCATION=$(az group show -n "$RG" --query location -o tsv)
echo "Resource group $RG is in $LOCATION"

# ---------------------------------------------------------------- 1. SQL server and databases
if ! az sql server show -n "$SQL_SERVER" -g "$RG" -o none 2>/dev/null; then
  az sql server create -n "$SQL_SERVER" -g "$RG" -l "$LOCATION" \
    --admin-user "$SQL_ADMIN" --admin-password "$SQL_ADMIN_PASSWORD" -o none
fi

# Start and end 0.0.0.0 is Azure's special rule "allow Azure services", which lets the Container Apps in.
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 -o none

# Serverless: General Purpose, Gen5, 0.5 to 1 vCore, pauses when idle, 2 GB, locally redundant backups.
for service in content scheduling; do
  if ! az sql db show -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-$service-db" -o none 2>/dev/null; then
    az sql db create -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-$service-db" \
      --edition GeneralPurpose --family Gen5 --compute-model Serverless \
      --min-capacity 0.5 --capacity 1 --auto-pause-delay "$AUTO_PAUSE_MINUTES" \
      --max-size 2GB --backup-storage-redundancy Local -o none
  fi
done

# ---------------------------------------------------------------- 2. One login per service
# Open the firewall for this machine only while the SQL files run, and close it again whatever happens.
MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-setup" \
  --start-ip-address "$MY_IP" --end-ip-address "$MY_IP" -o none
trap 'az sql server firewall-rule delete -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-setup" -o none' EXIT

# sqlcmd runs from the SQL Server image, so nothing has to be installed. It reads the admin password
# from SQLCMDPASSWORD and the $(...) variables of the SQL files from the environment.
run_sql() {  # run_sql <database> <file> [extra docker -e arguments]
  local database=$1 file=$2
  shift 2
  SQLCMDPASSWORD=$SQL_ADMIN_PASSWORD docker run --rm --platform linux/amd64 \
    -e SQLCMDPASSWORD "$@" -v "$PWD/infra:/infra:ro" \
    mcr.microsoft.com/mssql/server:2022-latest \
    /opt/mssql-tools18/bin/sqlcmd -S "$SQL_HOST" -U "$SQL_ADMIN" -d "$database" -i "/infra/$file" -b -l 120
}

run_sql master azure-logins.sql \
  -e CONTENT_PASSWORD="$CONTENT_DB_PASSWORD" -e SCHEDULING_PASSWORD="$SCHEDULING_DB_PASSWORD"
run_sql "$PREFIX-content-db" azure-user.sql -e SERVICE_USER=content_user
run_sql "$PREFIX-scheduling-db" azure-user.sql -e SERVICE_USER=scheduling_user

# ---------------------------------------------------------------- 3. Static Web App (Free)
if ! az staticwebapp show -n "$SWA" -g "$RG" -o none 2>/dev/null; then
  az staticwebapp create -n "$SWA" -g "$RG" -l "$SWA_LOCATION" --sku Free -o none
fi
UI_ORIGIN=https://$(az staticwebapp show -n "$SWA" -g "$RG" --query defaultHostname -o tsv)
echo "UI origin: $UI_ORIGIN"

# ---------------------------------------------------------------- 4. Container Apps
# --logs-destination none: no Log Analytics workspace is created, so nothing outside the allowance exists.
if ! az containerapp env show -n "$ENVIRONMENT" -g "$RG" -o none 2>/dev/null; then
  az containerapp env create -n "$ENVIRONMENT" -g "$RG" -l "$LOCATION" --logs-destination none -o none
fi

# Each app starts on a placeholder image. The first real image is deployed by the pipeline, which later
# changes only the image and GIT_SHA. The database URL is stored as a Container App secret, and the
# DATABASE_URL variable only refers to it (secretref).
create_app() {  # create_app <service> <db user> <db password> [extra env vars]
  local service=$1 user=$2 password=$3
  shift 3
  if az containerapp show -n "$PREFIX-$service" -g "$RG" -o none 2>/dev/null; then
    return
  fi
  az containerapp create -n "$PREFIX-$service" -g "$RG" --environment "$ENVIRONMENT" \
    --image "$PLACEHOLDER_IMAGE" --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
    --secrets "database-url=mssql://$user:$password@$SQL_HOST:1433/$PREFIX-$service-db" \
    --env-vars DATABASE_URL=secretref:database-url "UI_ORIGIN=$UI_ORIGIN" GIT_SHA=setup "$@" -o none
}

create_app content content_user "$CONTENT_DB_PASSWORD"
CONTENT_FQDN=$(az containerapp show -n "$PREFIX-content" -g "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
create_app scheduling scheduling_user "$SCHEDULING_DB_PASSWORD" \
  "CONTENT_URL=https://$CONTENT_FQDN" CONTENT_TIMEOUT_S=2

# ---------------------------------------------------------------- 5. What exists now
az resource list -g "$RG" --query "[?starts_with(name, '$PREFIX')].{name:name, type:type}" -o table
echo
echo "Public URL (system.yaml public_url, README): $UI_ORIGIN"
echo "GitHub secret SWA_DEPLOY_TOKEN: run the next line and paste its output into GitHub, nowhere else"
echo "  az staticwebapp secrets list -n $SWA -g $RG --query properties.apiKey -o tsv"
