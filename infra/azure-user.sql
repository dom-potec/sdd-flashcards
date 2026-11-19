-- Azure only, run against ONE service database by infra/azure-setup.sh, with $(SERVICE_USER) and
-- $(SERVICE_PASSWORD) taken by sqlcmd from environment variables set for that one run. The password is
-- not in this file.
-- The user is contained: it exists only inside this database and has no server login, so the content
-- user cannot open the scheduling database and the other way round.
-- Same roles as db/init.sql gives locally. Safe to run again: an existing user gets the new password.

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$(SERVICE_USER)')
    CREATE USER [$(SERVICE_USER)] WITH PASSWORD = '$(SERVICE_PASSWORD)';
ELSE
    ALTER USER [$(SERVICE_USER)] WITH PASSWORD = '$(SERVICE_PASSWORD)';
GO

ALTER ROLE db_ddladmin   ADD MEMBER [$(SERVICE_USER)];   -- CREATE and ALTER TABLE, for migrations
ALTER ROLE db_datareader ADD MEMBER [$(SERVICE_USER)];
ALTER ROLE db_datawriter ADD MEMBER [$(SERVICE_USER)];
GO
