-- Rename profile column to birthdate (API + Prisma field alignment)
ALTER TABLE "users" RENAME COLUMN "birthday" TO "birthdate";
