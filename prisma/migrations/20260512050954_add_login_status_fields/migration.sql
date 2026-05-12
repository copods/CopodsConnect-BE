-- AlterTable
ALTER TABLE "users" ADD COLUMN     "has_logged_in_app" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "has_logged_in_panel" BOOLEAN NOT NULL DEFAULT false;
