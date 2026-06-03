-- CreateTable
CREATE TABLE "appreciation_types" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "emoji" TEXT NOT NULL,
    "animation_url" TEXT,
    "description" TEXT,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "display_order" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "appreciation_types_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "appreciations" (
    "id" TEXT NOT NULL,
    "sender_id" TEXT NOT NULL,
    "appreciation_type_id" TEXT NOT NULL,
    "message" TEXT,
    "deleted_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "appreciations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "appreciation_recipients" (
    "id" TEXT NOT NULL,
    "appreciation_id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "seen_at" TIMESTAMP(3),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "appreciation_recipients_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "appreciations_sender_id_idx" ON "appreciations"("sender_id");

-- CreateIndex
CREATE INDEX "appreciations_deleted_at_idx" ON "appreciations"("deleted_at");

-- CreateIndex
CREATE INDEX "appreciation_recipients_user_id_idx" ON "appreciation_recipients"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "appreciation_recipients_appreciation_id_user_id_key" ON "appreciation_recipients"("appreciation_id", "user_id");

-- AddForeignKey
ALTER TABLE "appreciations" ADD CONSTRAINT "appreciations_sender_id_fkey" FOREIGN KEY ("sender_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "appreciations" ADD CONSTRAINT "appreciations_appreciation_type_id_fkey" FOREIGN KEY ("appreciation_type_id") REFERENCES "appreciation_types"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "appreciation_recipients" ADD CONSTRAINT "appreciation_recipients_appreciation_id_fkey" FOREIGN KEY ("appreciation_id") REFERENCES "appreciations"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "appreciation_recipients" ADD CONSTRAINT "appreciation_recipients_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
