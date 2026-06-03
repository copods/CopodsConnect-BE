-- CreateEnum
CREATE TYPE "AlertAction" AS ENUM ('RESTORED', 'CONFIRMED_REMOVAL', 'AUTO_REMOVED');

-- CreateTable
CREATE TABLE "admin_alerts" (
    "id" TEXT NOT NULL,
    "post_id" TEXT NOT NULL,
    "reported_user_id" TEXT NOT NULL,
    "flag_details" TEXT,
    "resolved_at" TIMESTAMP(3),
    "resolved_by_id" TEXT,
    "resolved_action" "AlertAction",
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "admin_alerts_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "admin_alerts_resolved_action_idx" ON "admin_alerts"("resolved_action");

-- CreateIndex
CREATE INDEX "admin_alerts_reported_user_id_idx" ON "admin_alerts"("reported_user_id");

-- AddForeignKey
ALTER TABLE "admin_alerts" ADD CONSTRAINT "admin_alerts_post_id_fkey" FOREIGN KEY ("post_id") REFERENCES "posts"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "admin_alerts" ADD CONSTRAINT "admin_alerts_reported_user_id_fkey" FOREIGN KEY ("reported_user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "admin_alerts" ADD CONSTRAINT "admin_alerts_resolved_by_id_fkey" FOREIGN KEY ("resolved_by_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
