/*
  Warnings:

  - You are about to drop the `workspace_members` table. If the table is not empty, all the data it contains will be lost.
  - You are about to drop the `workspaces` table. If the table is not empty, all the data it contains will be lost.

*/
-- DropForeignKey
ALTER TABLE "workspace_members" DROP CONSTRAINT "workspace_members_user_id_fkey";

-- DropForeignKey
ALTER TABLE "workspace_members" DROP CONSTRAINT "workspace_members_workspace_id_fkey";

-- DropForeignKey
ALTER TABLE "workspaces" DROP CONSTRAINT "workspaces_owner_id_fkey";

-- AlterTable
ALTER TABLE "users" ADD COLUMN     "ban_reason" TEXT,
ADD COLUMN     "banned_until" TIMESTAMP(3),
ADD COLUMN     "birthdate" TIMESTAMP(3),
ADD COLUMN     "date_of_joining" TIMESTAMP(3),
ADD COLUMN     "deleted_at" TIMESTAMP(3),
ADD COLUMN     "designation" TEXT,
ADD COLUMN     "has_logged_in_app" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "has_logged_in_panel" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "is_banned" BOOLEAN NOT NULL DEFAULT false;

-- DropTable
DROP TABLE "workspace_members";

-- DropTable
DROP TABLE "workspaces";

-- DropEnum
DROP TYPE "WorkspaceRole";

-- CreateIndex
CREATE INDEX "users_deleted_at_idx" ON "users"("deleted_at");

-- CreateIndex
CREATE INDEX "users_is_banned_idx" ON "users"("is_banned");

-- CreateIndex
CREATE INDEX "users_has_logged_in_app_idx" ON "users"("has_logged_in_app");

-- CreateIndex
CREATE INDEX "users_has_logged_in_panel_idx" ON "users"("has_logged_in_panel");

-- CreateIndex
CREATE INDEX "users_role_deleted_at_idx" ON "users"("role", "deleted_at");

-- CreateIndex
CREATE INDEX "users_is_banned_deleted_at_idx" ON "users"("is_banned", "deleted_at");

-- CreateIndex
CREATE INDEX "users_has_logged_in_app_is_banned_deleted_at_idx" ON "users"("has_logged_in_app", "is_banned", "deleted_at");

-- CreateIndex
CREATE INDEX "users_has_logged_in_panel_is_banned_deleted_at_idx" ON "users"("has_logged_in_panel", "is_banned", "deleted_at");
