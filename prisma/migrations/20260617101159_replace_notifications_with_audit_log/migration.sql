/*
  Warnings:

  - You are about to drop the `notifications` table. If the table is not empty, all the data it contains will be lost.

*/
-- CreateEnum
CREATE TYPE "AuditActorType" AS ENUM ('USER', 'ADMIN', 'SYSTEM');

-- CreateEnum
CREATE TYPE "AuditEntityType" AS ENUM ('USER', 'POST', 'COMMENT', 'LIKE', 'APPRECIATION', 'APPRECIATION_TYPE', 'ALERT', 'INVITATION');

-- CreateEnum
CREATE TYPE "AuditEventType" AS ENUM ('USER_INVITED', 'USER_INVITATION_RESENT', 'USER_LOGIN_APP', 'USER_LOGIN_PANEL', 'USER_LOGOUT_APP', 'USER_LOGOUT_PANEL', 'USER_PROFILE_UPDATED', 'USER_AVATAR_UPDATED', 'USER_SOFT_DELETED', 'USER_RESTORED', 'USER_PERMANENTLY_DELETED', 'USER_BANNED', 'USER_BAN_UPDATED', 'USER_UNBANNED_MANUAL', 'USER_UNBANNED_AUTO', 'USER_ROLE_CHANGED', 'POST_CREATED', 'POST_SCAN_COMPLETED', 'POST_CAPTION_EDITED', 'POST_DELETED_BY_AUTHOR', 'POST_REMOVED_BY_ADMIN', 'POST_RESTORED_BY_ADMIN', 'POST_LIKED', 'POST_UNLIKED', 'USER_TAGGED_IN_POST', 'USER_UNTAGGED_FROM_POST', 'COMMENT_CREATED', 'COMMENT_SCAN_COMPLETED', 'COMMENT_EDITED', 'COMMENT_DELETED_BY_AUTHOR', 'COMMENT_REMOVED_BY_ADMIN', 'COMMENT_RESTORED_BY_ADMIN', 'USER_TAGGED_IN_COMMENT', 'APPRECIATION_TYPE_CREATED', 'APPRECIATION_TYPE_TOGGLED', 'APPRECIATION_SENT', 'ALERT_CREATED', 'ALERT_RESOLVED', 'USER_SEARCH_PERFORMED', 'USER_BAN_EXPIRED', 'USER_PURGED_BY_JOB', 'SYSTEM_BIRTHDAY_POST_CREATED', 'SYSTEM_ANNIVERSARY_POST_CREATED');

-- DropForeignKey
ALTER TABLE "notifications" DROP CONSTRAINT "notifications_recipient_id_fkey";

-- AlterTable
ALTER TABLE "admin_alerts" ADD COLUMN     "comment_id" TEXT;

-- DropTable
DROP TABLE "notifications";

-- DropEnum
DROP TYPE "NotificationType";

-- CreateTable
CREATE TABLE "audit_logs" (
    "id" TEXT NOT NULL,
    "event_type" "AuditEventType" NOT NULL,
    "actor_type" "AuditActorType" NOT NULL,
    "actor_id" TEXT,
    "entity_type" "AuditEntityType" NOT NULL,
    "entity_id" TEXT NOT NULL,
    "parent_entity_type" "AuditEntityType",
    "parent_entity_id" TEXT,
    "metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "user_notifications" (
    "id" TEXT NOT NULL,
    "audit_log_id" TEXT NOT NULL,
    "recipient_id" TEXT NOT NULL,
    "read_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "user_notifications_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "audit_logs_entity_type_entity_id_created_at_idx" ON "audit_logs"("entity_type", "entity_id", "created_at" DESC);

-- CreateIndex
CREATE INDEX "audit_logs_actor_id_created_at_idx" ON "audit_logs"("actor_id", "created_at" DESC);

-- CreateIndex
CREATE INDEX "audit_logs_event_type_created_at_idx" ON "audit_logs"("event_type", "created_at" DESC);

-- CreateIndex
CREATE INDEX "audit_logs_parent_entity_type_parent_entity_id_created_at_idx" ON "audit_logs"("parent_entity_type", "parent_entity_id", "created_at" DESC);

-- CreateIndex
CREATE INDEX "audit_logs_created_at_idx" ON "audit_logs"("created_at" DESC);

-- CreateIndex
CREATE INDEX "user_notifications_recipient_id_created_at_idx" ON "user_notifications"("recipient_id", "created_at" DESC);

-- CreateIndex
CREATE INDEX "user_notifications_recipient_id_read_at_idx" ON "user_notifications"("recipient_id", "read_at");

-- CreateIndex
CREATE UNIQUE INDEX "user_notifications_audit_log_id_recipient_id_key" ON "user_notifications"("audit_log_id", "recipient_id");

-- AddForeignKey
ALTER TABLE "admin_alerts" ADD CONSTRAINT "admin_alerts_comment_id_fkey" FOREIGN KEY ("comment_id") REFERENCES "comments"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "audit_logs" ADD CONSTRAINT "audit_logs_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "user_notifications" ADD CONSTRAINT "user_notifications_audit_log_id_fkey" FOREIGN KEY ("audit_log_id") REFERENCES "audit_logs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "user_notifications" ADD CONSTRAINT "user_notifications_recipient_id_fkey" FOREIGN KEY ("recipient_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
