-- 生产库账号数据（超星 passport 身份 + 权限）
-- 前提：已部署并重启过服务，users 表已由 database.py 的幂等迁移补上 uid/fid/realname 与 idx_users_uid。
-- 本文件不含密码字段（passport 用户 password 统一为空串），可重复执行。

BEGIN;

-- 贾敬锎 (uid=168034620)
UPDATE users SET uid = '168034620', fid = '354241', realname = '贾敬锎' WHERE username = '168034620' AND uid IS NULL;
INSERT INTO users
  (username, password, role, avatar, can_chat, can_admin, created_at, updated_at, uid, fid, realname)
VALUES
  ('168034620', '', 'user', '', 1, 1, 1789732161.848256, 1789732161.848256, '168034620', '354241', '贾敬锎')
ON CONFLICT(uid) DO UPDATE SET
  can_chat = excluded.can_chat,
  can_admin = excluded.can_admin,
  realname = excluded.realname,
  fid = excluded.fid;

COMMIT;

-- 校验：
-- SELECT id, username, uid, fid, realname, can_chat, can_admin FROM users WHERE uid IS NOT NULL;