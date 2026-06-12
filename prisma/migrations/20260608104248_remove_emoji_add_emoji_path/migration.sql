/*
  Warnings:

  - You are about to drop the column `animation_url` on the `appreciation_types` table. All the data in the column will be lost.
  - You are about to drop the column `emoji` on the `appreciation_types` table. All the data in the column will be lost.
  - A unique constraint covering the columns `[name]` on the table `appreciation_types` will be added. If there are existing duplicate values, this will fail.
  - Added the required column `emoji_path` to the `appreciation_types` table without a default value. This is not possible if the table is not empty.

*/
-- Step 1: Drop old columns and add emoji_path as nullable first
ALTER TABLE "appreciation_types" DROP COLUMN "animation_url",
DROP COLUMN "emoji",
ADD COLUMN "emoji_path" TEXT;

-- Step 2: Fill existing rows with a temporary placeholder so NOT NULL can be enforced
UPDATE "appreciation_types" SET "emoji_path" = 'assets/appreciation-emojis/placeholder.svg';

-- Step 3: Now enforce NOT NULL
ALTER TABLE "appreciation_types" ALTER COLUMN "emoji_path" SET NOT NULL;

-- Step 4: Add unique constraint on name (will fail if duplicates exist — that's intentional)
CREATE UNIQUE INDEX "appreciation_types_name_key" ON "appreciation_types"("name");