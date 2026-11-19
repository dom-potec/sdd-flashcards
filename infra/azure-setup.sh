#!/usr/bin/env bash
# One-time Azure setup for the flashcards system, following the course's A2 deployment guide.
# Run it by hand from the repo root, after `az login` and `az account set` to the Azure for Students
# subscription, and with `gh` signed in as the repository owner. After it, only the pipeline changes Azure.
#
# It creates, in the resource group rg-dpotec-ieu2024:
#   1 storage account serving the UI as a static website,
#   1 SQL server with 2 serverless databases on the free offer, and 1 contained user in each,
#   1 Container Apps environment (Azure adds its Log Analytics workspace) with 2 Container Apps,
#   1 managed identity that the GitHub pipeline signs in as (OIDC, no stored credential).
# Then it stores what the pipeline needs as GitHub secrets and variables.
#
# The script can be run again after a failure: resources that exist are kept.
# No password is typed, printed or written to a file. The three passwords are generated here, sent to
# Azure and to GitHub secrets, and forgotten when the script ends. Running it again sets new ones.
set -euo pipefail

PREFIX=dpotec-ieu2024
RG=rg-$PREFIX
LOCATION=${LOCATION:-swedencentral}        # must be one of the subscription's allowed regions
GH_REPO=dom-potec/sdd-flashcards
UI_STORAGE=${PREFIX//-/}ui                 # storage names allow no hyphens
SQL_SERVER=$PREFIX-sql
SQL_HOST=$SQL_SERVER.database.windows.net
SQL_ADMIN=sqladmin
ENVIRONMENT=$PREFIX-env
IDENTITY=$PREFIX-github
PLACEHOLDER_IMAGE=mcr.microsoft.com/k8se/quickstart:latest
READERS="amartini@faculty.ie.edu bserra@faculty.ie.edu"

# Letters and digits only, because the service passwords end up inside a URL. "Aa1" guarantees the
# upper case, lower case and digit that Azure SQL's password policy asks for.
new_password() { echo "Aa1$(openssl rand -hex 16)"; }
SQL_ADMIN_PASSWORD=$(new_password)
CONTENT_DB_PASSWORD=$(new_password)
SCHEDULING_DB_PASSWORD=$(new_password)

# ---------------------------------------------------------------- 0. Check where this is going
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
echo "Azure subscription: $(az account show --query name -o tsv) ($SUBSCRIPTION_ID)"
echo "Region:             $LOCATION"
echo "GitHub repository:  $GH_REPO, as $(gh api user --jq .login)"
read -r -p "Create the resources there? [y/N] " answer
[ "$answer" = y ] || exit 1

# ---------------------------------------------------------------- 1. Providers and resource group
for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage \
                Microsoft.ManagedIdentity; do
  az provider register --namespace "$provider" --wait
done
az group create -n "$RG" -l "$LOCATION" -o none
RG_ID=$(az group show -n "$RG" --query id -o tsv)

# ---------------------------------------------------------------- 2. The UI: a storage static website
if ! az storage account show -n "$UI_STORAGE" -g "$RG" -o none 2>/dev/null; then
  az storage account create -n "$UI_STORAGE" -g "$RG" -l "$LOCATION" \
    --kind StorageV2 --sku Standard_LRS --min-tls-version TLS1_2 -o none
fi
az storage blob service-properties update --account-name "$UI_STORAGE" --auth-mode key \
  --static-website --index-document index.html -o none
# The web endpoint is the system's public address and the only origin the services accept (CORS).
UI_ORIGIN=$(az storage account show -n "$UI_STORAGE" -g "$RG" --query primaryEndpoints.web -o tsv)
UI_ORIGIN=${UI_ORIGIN%/}
echo "UI origin: $UI_ORIGIN"

# ---------------------------------------------------------------- 3. SQL server and databases
if az sql server show -n "$SQL_SERVER" -g "$RG" -o none 2>/dev/null; then
  az sql server update -n "$SQL_SERVER" -g "$RG" --admin-password "$SQL_ADMIN_PASSWORD" -o none
else
  az sql server create -n "$SQL_SERVER" -g "$RG" -l "$LOCATION" \
    --admin-user "$SQL_ADMIN" --admin-password "$SQL_ADMIN_PASSWORD" -o none
fi

# Start and end 0.0.0.0 is Azure's special rule "allow Azure services", which lets the Container Apps in.
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 -o none

# Serverless: General Purpose, Gen5, 0.5 to 1 vCore, locally redundant backups, on the free offer.
# The free offer fixes the auto-pause delay (60 minutes) and the size (32 GB), so neither is passed.
for service in content scheduling; do
  if ! az sql db show -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-$service-db" -o none 2>/dev/null; then
    az sql db create -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-$service-db" \
      --edition GeneralPurpose --family Gen5 --compute-model Serverless \
      --min-capacity 0.5 --capacity 1 --backup-storage-redundancy Local \
      --use-free-limit true --free-limit-exhaustion-behavior AutoPause -o none
  fi
done

# ---------------------------------------------------------------- 4. One contained user per database
# Open the firewall for this machine only while the SQL file runs, and close it again whatever happens.
MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-setup" \
  --start-ip-address "$MY_IP" --end-ip-address "$MY_IP" -o none
trap 'az sql server firewall-rule delete -g "$RG" -s "$SQL_SERVER" -n "$PREFIX-setup" -o none' EXIT

# sqlcmd runs from the SQL Server image, so nothing has to be installed. It reads the admin password
# from SQLCMDPASSWORD and the $(...) variables of the SQL file from the environment. A new firewall
# rule or admin password can take a moment to apply, so a failed run is tried again a few times.
create_user() {  # create_user <database> <user> <password>
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if SQLCMDPASSWORD=$SQL_ADMIN_PASSWORD SERVICE_USER=$2 SERVICE_PASSWORD=$3 \
      docker run --rm --platform linux/amd64 \
        -e SQLCMDPASSWORD -e SERVICE_USER -e SERVICE_PASSWORD -v "$PWD/infra:/infra:ro" \
        mcr.microsoft.com/mssql/server:2022-latest \
        /opt/mssql-tools18/bin/sqlcmd -S "$SQL_HOST" -U "$SQL_ADMIN" -d "$1" \
        -i /infra/azure-user.sql -b -l 120; then
      return
    fi
    echo "sqlcmd on $1 failed (attempt $attempt of 6), trying again in 20 s"
    sleep 20
  done
  return 1
}

create_user "$PREFIX-content-db" content_user "$CONTENT_DB_PASSWORD"
create_user "$PREFIX-scheduling-db" scheduling_user "$SCHEDULING_DB_PASSWORD"

# ---------------------------------------------------------------- 5. Container Apps
# Azure creates a Log Analytics workspace with the environment, for the containers' logs. It is kept.
if ! az containerapp env show -n "$ENVIRONMENT" -g "$RG" -o none 2>/dev/null; then
  az containerapp env create -n "$ENVIRONMENT" -g "$RG" -l "$LOCATION" -o none
fi

# Each app starts on a placeholder image; the first deployment replaces it. The database URL is a
# Container App secret and DATABASE_URL only refers to it (secretref). CORS is done by the services
# themselves from UI_ORIGIN, so the ingress CORS setting stays off.
create_app() {  # create_app <service> <db user> <db password> [extra env vars]
  local service=$1 url="mssql://$2:$3@$SQL_HOST:1433/$PREFIX-$1-db"
  shift 3
  if az containerapp show -n "$PREFIX-$service" -g "$RG" -o none 2>/dev/null; then
    az containerapp secret set -n "$PREFIX-$service" -g "$RG" --secrets "database-url=$url" -o none
    return
  fi
  az containerapp create -n "$PREFIX-$service" -g "$RG" --environment "$ENVIRONMENT" \
    --image "$PLACEHOLDER_IMAGE" --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
    --secrets "database-url=$url" \
    --env-vars DATABASE_URL=secretref:database-url "UI_ORIGIN=$UI_ORIGIN" GIT_SHA=setup "$@" -o none
}

create_app content content_user "$CONTENT_DB_PASSWORD"
CONTENT_FQDN=$(az containerapp show -n "$PREFIX-content" -g "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)
create_app scheduling scheduling_user "$SCHEDULING_DB_PASSWORD" \
  "CONTENT_URL=https://$CONTENT_FQDN" CONTENT_TIMEOUT_S=2

# ---------------------------------------------------------------- 6. The pipeline's identity
# IE accounts cannot create service principals, so the pipeline signs in as a user-assigned managed
# identity through OIDC. It is Contributor on this resource group only.
az identity create -n "$IDENTITY" -g "$RG" -l "$LOCATION" -o none
CLIENT_ID=$(az identity show -n "$IDENTITY" -g "$RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show -n "$IDENTITY" -g "$RG" --query principalId -o tsv)
for attempt in 1 2 3 4 5 6; do   # a new identity takes a moment to be known to role assignments
  if az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal --role Contributor --scope "$RG_ID" -o none; then
    break
  fi
  [ "$attempt" -lt 6 ] || exit 1
  sleep 10
done

# GitHub's token names the repository and branch as its subject, either by name or with numeric ids.
# Both are registered, and only the main branch is trusted. ${GH_REPO} in braces: zsh would mangle :r.
OWNER_ID=$(gh api "repos/${GH_REPO}" --jq .owner.id)
REPO_ID=$(gh api "repos/${GH_REPO}" --jq .id)
federate() {  # federate <name> <subject>
  az identity federated-credential create --name "$1" --identity-name "$IDENTITY" -g "$RG" \
    --issuer https://token.actions.githubusercontent.com --subject "$2" \
    --audiences api://AzureADTokenExchange -o none
}
federate github-main "repo:${GH_REPO}:ref:refs/heads/main"
federate github-main-ids "repo:${GH_REPO%/*}@${OWNER_ID}/${GH_REPO#*/}@${REPO_ID}:ref:refs/heads/main"

# ---------------------------------------------------------------- 7. GitHub secrets and variables
set_secret() { printf '%s' "$2" | gh secret set "$1" --repo "$GH_REPO"; }
set_secret AZURE_CLIENT_ID "$CLIENT_ID"
set_secret AZURE_TENANT_ID "$TENANT_ID"
set_secret AZURE_SUBSCRIPTION_ID "$SUBSCRIPTION_ID"
set_secret CONTENT_DB_PASSWORD "$CONTENT_DB_PASSWORD"
set_secret SCHEDULING_DB_PASSWORD "$SCHEDULING_DB_PASSWORD"
gh variable set PREFIX --repo "$GH_REPO" --body "$PREFIX"
gh variable set RESOURCE_GROUP --repo "$GH_REPO" --body "$RG"
gh variable set UI_STORAGE --repo "$GH_REPO" --body "$UI_STORAGE"

# ---------------------------------------------------------------- 8. Read access for the professors
for reader in $READERS; do
  az role assignment create --assignee "$reader" --role Reader --scope "$RG_ID" -o none \
    || echo "WARNING: could not give Reader to $reader; do it in the portal (resource group > Access control)"
done

# ---------------------------------------------------------------- 9. What exists now
az resource list -g "$RG" --query "[].{name:name, type:type}" -o table
echo
echo "Public URL (system.yaml public_url, README): $UI_ORIGIN"
