from concurrent.futures import ThreadPoolExecutor
# import os

# from dotenv import load_dotenv
# import redshift_connector
# from sqlalchemy.engine.url import make_url
# from sqlalchemy.pool import QueuePool

# load_dotenv('.env.local')


def parallelize(funcs):
    """Execute functions in parallel and return results in same order.

    Args:
        funcs: List of (fn, args, kwargs) tuples or (fn, args) tuples

    Returns:
        List of results in same order as input
    """
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(fn, *args, **(kwargs if len(item) > 2 else {}))
            for item in funcs
            for fn, args, kwargs in [(item[0], item[1], item[2] if len(item) > 2 else {})]
        ]
    return [f.result() for f in futures]

# REDSHIFT_CONN = f'postgresql://ahaslides:{os.environ["REDSHIFT_PASSWORD"]}@us01-datawarehouse-report.cps9bf1es8tr.us-east-1.redshift.amazonaws.com:5439/report'
#
#
# @st.cache_resource
# def get_redshift_pool():
#     parsed = make_url(REDSHIFT_CONN)
#
#     def create_conn():
#         return redshift_connector.connect(
#             host=parsed.host,
#             port=parsed.port,
#             database=parsed.database,
#             user=parsed.username,
#             password=parsed.password
#         )
#
#     return QueuePool(
#         create_conn,
#         pool_size=1,  # TODO: revert to pool_size=5
#         max_overflow=0,  # TODO: revert to max_overflow=10
#         recycle=1800
#     )
#
#
# def redshift_execute(sql: str, _retry: bool = True):
#     pool = get_redshift_pool()
#     conn = pool.connect()
#     try:
#         cursor = conn.cursor()
#         cursor.execute(sql)
#         rows = cursor.fetchall()
#         columns = [desc[0] for desc in cursor.description]
#         return [dict(zip(columns, row)) for row in rows]
#     # This exception is mainly for catching BrokenPipe error. This might happens if the connection is somehow killed
#     # or if it's idle for too long. We simply invalidate the connection and try again.
#     # Since TCP connections can be half-open, the only ways to handle connection error is to preping/using keep-alive
#     # or handle error as they happen and retry.
#     # For preping/keepalive, SA has a pool_pre_ping option which due to some versioning/package mismatch is unusable.
#     # Prepinging adds quite a bit of overhead anyway.
#     # So we opted for the other option: recycle connections regularly and retry if we see errors.
#     # To test session termination, use `pid = redshift_execute("SELECT pg_backend_pid() as pid")[0]['pid']` to get session id
#     # then run `pg_terminate_backend(pid)` in a db client to kill the session.
#     except Exception:
#         conn.invalidate()
#         if _retry:
#             return redshift_execute(sql, _retry=False)
#         raise
#     finally:
#         conn.close()
