-- Azure only, run once against ONE service database by infra/azure-setup.sh, with $(SERVICE_USER)
-- set to that service's login. Azure SQL Database has no USE statement, so the script is run once per
-- database instead. The login gets a user in its own database only: it cannot open the other one.
-- Same roles as db/init.sql gives locally. Safe to run again.

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$(SERVICE_USER)')
    CREATE USER [$(SERVICE_USER)] FOR LOGIN [$(SERVICE_USER)];
GO

ALTER ROLE db_ddladmin   ADD MEMBER [$(SERVICE_USER)];   -- CREATE and ALTER TABLE, for migrations
ALTER ROLE db_datareader ADD MEMBER [$(SERVICE_USER)];
ALTER ROLE db_datawriter ADD MEMBER [$(SERVICE_USER)];
GO
