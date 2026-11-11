-- Local development only. Creates the databases and one login per service on the compose SQL Server.
-- Safe to run again: every statement checks before it creates.
-- The passwords here are local-only development credentials and are never used on Azure.
-- GO separates batches, because USE and CREATE DATABASE cannot share a batch with what follows.

IF DB_ID('content')         IS NULL CREATE DATABASE content;
IF DB_ID('scheduling')      IS NULL CREATE DATABASE scheduling;
IF DB_ID('content_test')    IS NULL CREATE DATABASE content_test;      -- local unit tests
IF DB_ID('scheduling_test') IS NULL CREATE DATABASE scheduling_test;
GO

IF SUSER_ID('content_user')    IS NULL CREATE LOGIN content_user    WITH PASSWORD = 'ContentDev_Passw0rd',    CHECK_POLICY = OFF;
IF SUSER_ID('scheduling_user') IS NULL CREATE LOGIN scheduling_user WITH PASSWORD = 'SchedulingDev_Passw0rd', CHECK_POLICY = OFF;
GO

-- content_user exists only in the content database: it cannot open scheduling.
USE content;
IF USER_ID('content_user') IS NULL CREATE USER content_user FOR LOGIN content_user;
ALTER ROLE db_ddladmin   ADD MEMBER content_user;   -- CREATE and ALTER TABLE, for migrations
ALTER ROLE db_datareader ADD MEMBER content_user;
ALTER ROLE db_datawriter ADD MEMBER content_user;
GO

-- scheduling_user exists only in the scheduling database: it cannot open content.
USE scheduling;
IF USER_ID('scheduling_user') IS NULL CREATE USER scheduling_user FOR LOGIN scheduling_user;
ALTER ROLE db_ddladmin   ADD MEMBER scheduling_user;
ALTER ROLE db_datareader ADD MEMBER scheduling_user;
ALTER ROLE db_datawriter ADD MEMBER scheduling_user;
GO
