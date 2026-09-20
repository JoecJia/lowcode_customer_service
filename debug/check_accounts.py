"""部署辅助：动态判断生产库账号数据（prod_accounts.sql）是否需要执行。

用法::

    python debug/check_accounts.py            # 只检查，不修改任何数据
    python debug/check_accounts.py --apply    # 需要时自动迁移并执行 prod_accounts.sql

退出码（便于接入部署流水线）::

    0 = SKIP          已一致，无需执行
    2 = APPLY         需要执行（账号缺失或权限/信息不一致）
    3 = MIGRATE_FIRST 库结构未迁移（缺 uid 列或唯一索引）→ 需先重启服务
    1 = ERROR         其他异常（文件缺失、SQL 解析失败等）

说明：prod_accounts.sql 本身是幂等的，重复执行永远安全；本脚本只是让流水线
能"按需执行"并给出可读的差异，不改变最终结果。
"""

import argparse
import csv
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from config import DB_PATH  # noqa: E402

SQL_FILE = os.path.join(ROOT, "prod_accounts.sql")
REQUIRED_COLUMNS = {"uid", "fid", "realname"}
REQUIRED_INDEX = "idx_users_uid"

# INSERT 语句中的列顺序（与 prod_accounts.sql 保持一致）
INSERT_COLUMNS = [
    "username",
    "password",
    "role",
    "avatar",
    "can_chat",
    "can_admin",
    "created_at",
    "updated_at",
    "uid",
    "fid",
    "realname",
]

_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+users\s*\((.*?)\)\s*VALUES\s*\((.*?)\)", re.IGNORECASE | re.DOTALL
)

EXIT_SKIP = 0
EXIT_ERROR = 1
EXIT_APPLY = 2
EXIT_MIGRATE_FIRST = 3


def parse_expected(sql_text: str) -> list[dict]:
    """从 prod_accounts.sql 解析出期望的账号行。"""
    expected: list[dict] = []
    for columns_text, values_text in _INSERT_RE.findall(sql_text):
        columns = [c.strip() for c in columns_text.split(",")]
        # SQL 用单引号做字符串字面量，csv 默认只识别双引号，这里显式指定
        values = next(csv.reader([values_text], skipinitialspace=True, quotechar="'"))
        row = {k: (v.strip() if isinstance(v, str) else v) for k, v in zip(columns, values)}
        uid = str(row.get("uid", "")).strip()
        if not uid:
            continue
        expected.append(
            {
                "uid": uid,
                "fid": str(row.get("fid", "")).strip(),
                "realname": str(row.get("realname", "")).strip(),
                "can_chat": int(float(row.get("can_chat") or 0)),
                "can_admin": int(float(row.get("can_admin") or 0)),
            }
        )
    return expected


def check_migration(conn: sqlite3.Connection) -> list[str]:
    columns = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    indexes = {r[1] for r in conn.execute("PRAGMA index_list(users)")}
    missing = sorted(REQUIRED_COLUMNS - columns)
    if REQUIRED_INDEX not in indexes:
        missing.append(REQUIRED_INDEX)
    return missing


def diff_accounts(conn: sqlite3.Connection, expected: list[dict]) -> list[str]:
    """返回差异描述列表，空列表表示已一致。"""
    conn.row_factory = sqlite3.Row
    diffs: list[str] = []
    for want in expected:
        row = conn.execute(
            "SELECT fid, realname, can_chat, can_admin FROM users WHERE uid = ?",
            (want["uid"],),
        ).fetchone()
        if row is None:
            diffs.append(f"uid={want['uid']} 账号不存在")
            continue
        actual = {
            "fid": row["fid"] or "",
            "realname": row["realname"] or "",
            "can_chat": int(row["can_chat"] or 0),
            "can_admin": int(row["can_admin"] or 0),
        }
        for field in ("fid", "realname", "can_chat", "can_admin"):
            if actual[field] != want[field]:
                diffs.append(
                    f"uid={want['uid']} {field}: 当前={actual[field]!r} 期望={want[field]!r}"
                )
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="需要时执行 prod_accounts.sql")
    args = parser.parse_args()

    if not os.path.isfile(SQL_FILE):
        print(f"DECISION=ERROR  未找到 {SQL_FILE}")
        return EXIT_ERROR

    with open(SQL_FILE, encoding="utf-8") as f:
        sql_text = f.read()

    expected = parse_expected(sql_text)
    if not expected:
        print("DECISION=ERROR  prod_accounts.sql 中未解析到任何账号")
        return EXIT_ERROR

    print(f"[db] {DB_PATH}")
    print(f"[sql] 期望账号 {len(expected)} 条: " + ", ".join(e["uid"] for e in expected))

    if args.apply:
        # 通过业务入口触发一次幂等迁移（与服务启动时走的是同一段逻辑）
        import database  # noqa: PLC0415

        database.get_db()

    conn = sqlite3.connect(DB_PATH)
    try:
        missing = check_migration(conn)
        if missing:
            print(f"[migrate] 缺少 {', '.join(missing)}")
            print("DECISION=MIGRATE_FIRST  请先重启服务（或加 --apply 让脚本自动迁移）")
            return EXIT_MIGRATE_FIRST

        diffs = diff_accounts(conn, expected)
        if not diffs:
            print("[check] 账号数据已一致")
            print("DECISION=SKIP  无需执行 prod_accounts.sql")
            return EXIT_SKIP

        print("[check] 存在差异：")
        for line in diffs:
            print("  - " + line)

        if args.apply:
            conn.executescript(sql_text)
            conn.commit()
            remain = diff_accounts(conn, expected)
            if remain:
                print("[apply] 执行后仍有差异：")
                for line in remain:
                    print("  - " + line)
                print("DECISION=ERROR")
                return EXIT_ERROR
            print("[apply] 已执行 prod_accounts.sql 并核对通过")
            print("DECISION=APPLIED")
            return EXIT_SKIP

        print("DECISION=APPLY  需要执行 prod_accounts.sql（或加 --apply 直接执行）")
        return EXIT_APPLY
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
