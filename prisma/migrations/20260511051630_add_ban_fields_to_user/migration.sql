-- AlterTable
ALTER TABLE "users" ADD COLUMN     "banned_until" TIMESTAMP(3),
ADD COLUMN     "is_banned" BOOLEAN NOT NULL DEFAULT false;
