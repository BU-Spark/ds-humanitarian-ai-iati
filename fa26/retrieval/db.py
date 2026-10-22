"""
db.py -- the one place the retrieval layer talks to Neo4j.

* connection details come from .env (retrieval/../.env first, then its parent)
* every query runs inside a READ transaction: the server rejects writes
  (Neo.ClientError.Statement.AccessMode), which is the read-only guarantee
  we can get on Aura Free / Community Edition where roles are unavailable
* every query gets a transaction timeout and must contain a LIMIT
* Neo4j temporal values are converted to ISO strings so rows are JSON-ready
"""
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, unit_of_work
from neo4j.time import Date, DateTime, Duration, Time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_TIMEOUT_S = 30
_driver = None
_database = None


def load_env(path=None):
    """Load the first .env found. Returns its path or None."""
    for p in ([Path(path)] if path else [ROOT / ".env", ROOT.parent / ".env"]):
        if p.exists():
            logging.getLogger("dotenv").setLevel(logging.ERROR)  # Aura .env has a bare URL line
            load_dotenv(p, override=False)
            return p
    return None


def get_driver():
    """Lazy singleton driver. Raises RuntimeError with a clear message if .env is incomplete."""
    global _driver, _database
    if _driver is None:
        load_env(os.environ.get("RETRIEVAL_ENV"))
        missing = [k for k in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"Neo4j connection: missing {missing} in .env")
        _driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                                       auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
                                       connection_timeout=5, max_transaction_retry_time=5.0)
        _database = os.environ.get("NEO4J_DATABASE") or None
    return _driver


def close():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def _plain(v):
    """neo4j temporal types -> ISO strings; recurse into lists/dicts."""
    if isinstance(v, (Date, DateTime, Time)):
        return v.iso_format()
    if isinstance(v, Duration):
        return str(v)
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


_LIMIT_RE = re.compile(r"\bLIMIT\s+(\$\w+|\d+)\s*$", re.I)


def read_query(cypher, params=None, timeout=DEFAULT_TIMEOUT_S):
    """Run a read-only Cypher query; returns a list of plain dicts.

    Refuses queries that do not end in LIMIT so no tool can return an
    unbounded result. Parameters are always passed as $params, never
    formatted into the string.
    """
    if not _LIMIT_RE.search(cypher.strip()):
        raise ValueError("read_query: Cypher must end with a LIMIT clause")
    params = params or {}

    @unit_of_work(timeout=timeout)
    def work(tx):
        return tx.run(cypher, params).data()

    driver = get_driver()
    with driver.session(database=_database, default_access_mode="READ") as s:
        return [_plain(r) for r in s.execute_read(work)]
