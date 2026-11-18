-- Azure only, run once against the master database by infra/azure-setup.sh.
-- Creates one server login per service. The passwords are not in this file: sqlcmd replaces
-- $(CONTENT_PASSWORD) and $(SCHEDULING_PASSWORD) with environment variables set for that one run.
-- Safe to run again: each login is created only if it does not exist.

IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'content_user')
    CREATE LOGIN content_user WITH PASSWORD = '$(CONTENT_PASSWORD)';
GO

IF NOT EXISTS (SELECT 1 FROM sys.sql_logins WHERE name = 'scheduling_user')
    CREATE LOGIN scheduling_user WITH PASSWORD = '$(SCHEDULING_PASSWORD)';
GO
