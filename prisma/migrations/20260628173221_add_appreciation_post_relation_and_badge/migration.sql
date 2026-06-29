/*
  Warnings:

  - A unique constraint covering the columns `[post_id]` on the table `appreciations` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `badge_path` to the `appreciation_types` table without a default value. This is not possible if the table is not empty.
  - Added the required column `post_id` to the `appreciations` table without a default value. This is not possible if the table is not empty.

*/
-- DropForeignKey
ALTER TABLE "admin_alerts" DROP CONSTRAINT "admin_alerts_reported_user_id_fkey";

-- DropForeignKey
ALTER TABLE "admin_alerts" DROP CONSTRAINT "admin_alerts_resolved_by_id_fkey";

-- DropForeignKey
ALTER TABLE "appreciation_recipients" DROP CONSTRAINT "appreciation_recipients_appreciation_id_fkey";

-- DropForeignKey
ALTER TABLE "appreciation_recipients" DROP CONSTRAINT "appreciation_recipients_user_id_fkey";

-- DropForeignKey
ALTER TABLE "appreciations" DROP CONSTRAINT "appreciations_sender_id_fkey";

-- DropForeignKey
ALTER TABLE "comment_tags" DROP CONSTRAINT "comment_tags_tagged_user_id_fkey";

-- DropForeignKey
ALTER TABLE "comments" DROP CONSTRAINT "comments_author_id_fkey";

-- DropForeignKey
ALTER TABLE "likes" DROP CONSTRAINT "likes_user_id_fkey";

-- DropForeignKey
ALTER TABLE "moderation_blacklist" DROP CONSTRAINT "moderation_blacklist_added_by_id_fkey";

-- DropForeignKey
ALTER TABLE "moderation_whitelist" DROP CONSTRAINT "moderation_whitelist_added_by_id_fkey";

-- DropForeignKey
ALTER TABLE "post_tags" DROP CONSTRAINT "post_tags_tagged_user_id_fkey";

-- DropForeignKey
ALTER TABLE "posts" DROP CONSTRAINT "posts_author_id_fkey";

-- DropForeignKey
ALTER TABLE "user_notifications" DROP CONSTRAINT "user_notifications_recipient_id_fkey";

-- AlterTable
ALTER TABLE "appreciation_types" ADD COLUMN     "badge_path" TEXT NOT NULL;

-- AlterTable
ALTER TABLE "appreciations" ADD COLUMN     "post_id" TEXT NOT NULL;

-- AlterTable
ALTER TABLE "moderation_blacklist" ALTER COLUMN "added_by_id" DROP NOT NULL;

-- AlterTable
ALTER TABLE "moderation_whitelist" ALTER COLUMN "added_by_id" DROP NOT NULL;

-- CreateIndex
CREATE UNIQUE INDEX "appreciations_post_id_key" ON "appreciations"("post_id");

-- AddForeignKey
ALTER TABLE "posts" ADD CONSTRAINT "posts_author_id_fkey" FOREIGN KEY ("author_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "post_tags" ADD CONSTRAINT "post_tags_tagged_user_id_fkey" FOREIGN KEY ("tagged_user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "likes" ADD CONSTRAINT "likes_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "comments" ADD CONSTRAINT "comments_author_id_fkey" FOREIGN KEY ("author_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "comment_tags" ADD CONSTRAINT "comment_tags_tagged_user_id_fkey" FOREIGN KEY ("tagged_user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "appreciations" ADD CONSTRAINT "appreciations_sender_id_fkey" FOREIGN KEY ("sender_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "appreciations" ADD CONSTRAINT "appreciations_post_id_fkey" FOREIGN KEY ("post_id") REFERENCES "posts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "appreciation_recipients" ADD CONSTRAINT "appreciation_recipients_appreciation_id_fkey" FOREIGN KEY ("appreciation_id") REFERENCES "appreciations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "appreciation_recipients" ADD CONSTRAINT "appreciation_recipients_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "admin_alerts" ADD CONSTRAINT "admin_alerts_reported_user_id_fkey" FOREIGN KEY ("reported_user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "admin_alerts" ADD CONSTRAINT "admin_alerts_resolved_by_id_fkey" FOREIGN KEY ("resolved_by_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "moderation_blacklist" ADD CONSTRAINT "moderation_blacklist_added_by_id_fkey" FOREIGN KEY ("added_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "moderation_whitelist" ADD CONSTRAINT "moderation_whitelist_added_by_id_fkey" FOREIGN KEY ("added_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "user_notifications" ADD CONSTRAINT "user_notifications_recipient_id_fkey" FOREIGN KEY ("recipient_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
