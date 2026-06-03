-- CreateTable
CREATE TABLE "comment_tags" (
    "id" TEXT NOT NULL,
    "comment_id" TEXT NOT NULL,
    "tagged_user_id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "comment_tags_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "comment_tags_tagged_user_id_idx" ON "comment_tags"("tagged_user_id");

-- CreateIndex
CREATE UNIQUE INDEX "comment_tags_comment_id_tagged_user_id_key" ON "comment_tags"("comment_id", "tagged_user_id");

-- AddForeignKey
ALTER TABLE "comment_tags" ADD CONSTRAINT "comment_tags_comment_id_fkey" FOREIGN KEY ("comment_id") REFERENCES "comments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "comment_tags" ADD CONSTRAINT "comment_tags_tagged_user_id_fkey" FOREIGN KEY ("tagged_user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
