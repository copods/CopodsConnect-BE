-- CreateEnum
CREATE TYPE "NotificationType" AS ENUM ('POST_LIKE', 'POST_COMMENT', 'POST_TAG', 'COMMENT_REPLY', 'COMMENT_TAG', 'APPRECIATION_RECEIVED', 'BIRTHDAY_CELEBRATION', 'ANNIVERSARY_CELEBRATION', 'PEER_BIRTHDAY', 'PEER_ANNIVERSARY', 'POST_REMOVED_BY_MODERATION', 'LEADERBOARD_DIGEST');

-- CreateTable
CREATE TABLE "notifications" (
    "id" TEXT NOT NULL,
    "recipient_id" TEXT NOT NULL,
    "type" "NotificationType" NOT NULL,
    "actor_ids" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "entity_type" TEXT,
    "entity_id" TEXT,
    "metadata" JSONB,
    "is_read" BOOLEAN NOT NULL DEFAULT false,
    "read_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "notifications_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "notifications_recipient_id_is_read_created_at_idx" ON "notifications"("recipient_id", "is_read", "created_at" DESC);

-- CreateIndex
CREATE INDEX "notifications_recipient_id_type_entity_id_is_read_idx" ON "notifications"("recipient_id", "type", "entity_id", "is_read");

-- CreateIndex
CREATE INDEX "notifications_entity_type_entity_id_idx" ON "notifications"("entity_type", "entity_id");

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_recipient_id_fkey" FOREIGN KEY ("recipient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
