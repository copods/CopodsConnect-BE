-- Optional message shown to the user when access is restricted (see ban_check + API errors).
ALTER TABLE "users" ADD COLUMN "ban_reason" TEXT;
