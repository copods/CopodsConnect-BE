-- CreateIndex
CREATE INDEX "users_deleted_at_idx" ON "users"("deleted_at");

-- CreateIndex
CREATE INDEX "users_is_banned_idx" ON "users"("is_banned");

-- CreateIndex
CREATE INDEX "users_has_logged_in_app_idx" ON "users"("has_logged_in_app");

-- CreateIndex
CREATE INDEX "users_has_logged_in_panel_idx" ON "users"("has_logged_in_panel");

-- CreateIndex
CREATE INDEX "users_role_deleted_at_idx" ON "users"("role", "deleted_at");

-- CreateIndex
CREATE INDEX "users_is_banned_deleted_at_idx" ON "users"("is_banned", "deleted_at");

-- CreateIndex
CREATE INDEX "users_has_logged_in_app_is_banned_deleted_at_idx" ON "users"("has_logged_in_app", "is_banned", "deleted_at");

-- CreateIndex
CREATE INDEX "users_has_logged_in_panel_is_banned_deleted_at_idx" ON "users"("has_logged_in_panel", "is_banned", "deleted_at");
