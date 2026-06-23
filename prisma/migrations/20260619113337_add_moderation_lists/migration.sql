-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "AlertAction" ADD VALUE 'BLACKLISTED';
ALTER TYPE "AlertAction" ADD VALUE 'WHITELISTED';

-- AlterTable
ALTER TABLE "admin_alerts" ADD COLUMN     "flagged_phrase" TEXT;

-- CreateTable
CREATE TABLE "moderation_blacklist" (
    "id" TEXT NOT NULL,
    "raw_phrase" TEXT NOT NULL,
    "normalized_key" TEXT NOT NULL,
    "added_by_id" TEXT NOT NULL,
    "alert_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "moderation_blacklist_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "moderation_whitelist" (
    "id" TEXT NOT NULL,
    "raw_phrase" TEXT NOT NULL,
    "normalized_key" TEXT NOT NULL,
    "added_by_id" TEXT NOT NULL,
    "alert_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "moderation_whitelist_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "moderation_blacklist_normalized_key_key" ON "moderation_blacklist"("normalized_key");

-- CreateIndex
CREATE INDEX "moderation_blacklist_normalized_key_idx" ON "moderation_blacklist"("normalized_key");

-- CreateIndex
CREATE UNIQUE INDEX "moderation_whitelist_normalized_key_key" ON "moderation_whitelist"("normalized_key");

-- CreateIndex
CREATE INDEX "moderation_whitelist_normalized_key_idx" ON "moderation_whitelist"("normalized_key");

-- AddForeignKey
ALTER TABLE "moderation_blacklist" ADD CONSTRAINT "moderation_blacklist_added_by_id_fkey" FOREIGN KEY ("added_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "moderation_whitelist" ADD CONSTRAINT "moderation_whitelist_added_by_id_fkey" FOREIGN KEY ("added_by_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
