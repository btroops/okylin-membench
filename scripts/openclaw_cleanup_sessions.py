# -*- coding: utf-8 -*-
"""清理 OpenClaw 会话库中的 membench 孤儿会话（session_key 含 ':mb-'）。

在 gateway 停止后运行（避免 SQLite 锁与写入竞争）：
  docker compose run --rm --no-deps openclaw-gateway \
    python3 /home/node/.openclaw/cleanup_sessions.py
"""
import sqlite3

DB = "/home/node/.openclaw/agents/main/agent/openclaw-agent.sqlite"
PAT = "%:mb-%"          # 会话键形如 agent:main:mb-<uuid>[:sN|:probe:pN]
KEEP = "agent:main:main"  # 官方默认主会话，保留

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

tables = [r[0] for r in cur.execute(
    "select name from sqlite_master where type='table' and name not like '%fts%'")]

def cols(t):
    return [c[1] for c in cur.execute("pragma table_info(%s)" % t)]

# 1) 收集待删会话（mb-*）的 key 与 id
mb_keys = [r[0] for r in cur.execute(
    "select session_key from session_nodes where session_key like ? and session_key != ?",
    (PAT, KEEP))]
mb_ids = [r[0] for r in cur.execute(
    "select session_id from session_windows where session_key like ?", (PAT,))]
print("待删 session_key 数:", len(mb_keys), "| session_id 数:", len(mb_ids))

# 2) 干跑：各表将删除的行数
plan = []
for t in tables:
    cs = cols(t)
    if "session_key" in cs:
        n = cur.execute("select count(*) from %s where session_key like ? and session_key != ?" % t,
                        (PAT, KEEP)).fetchone()[0]
        plan.append((t, "session_key", n))
    elif "session_id" in cs:
        n = cur.execute(
            "select count(*) from %s where session_id in (select session_id from session_windows where session_key like ?)" % t,
            (PAT,)).fetchone()[0]
        plan.append((t, "session_id", n))
for t, how, n in plan:
    print("  %-34s by %-11s -> %d 行" % (t, how, n))

# 3) 执行删除（先 id 键表，后 key 键表，最后节点/窗口本身）
total = 0
for t, how, _n in plan:
    if how == "session_id":
        cur.execute(
            "delete from %s where session_id in (select session_id from session_windows where session_key like ?)" % t,
            (PAT,))
        total += cur.rowcount
for t, how, _n in plan:
    if how == "session_key":
        cur.execute("delete from %s where session_key like ? and session_key != ?" % t, (PAT, KEEP))
        total += cur.rowcount
con.commit()

# 4) 收尾：checkpoint + 统计
cur.execute("pragma wal_checkpoint(truncate)")
left = cur.execute("select count(*) from session_nodes").fetchone()[0]
print("删除总行数:", total, "| 剩余 session_nodes:", left)
for t in ("session_nodes", "session_windows", "transcript_events", "trajectory_runtime_events"):
    print("  剩余 %-26s %d" % (t, cur.execute("select count(*) from " + t).fetchone()[0]))
con.close()
print("DONE")
