"""Reusable Text2Cypher control flow; synthetic runs are not model evaluations."""
import json
import os
import re
from time import perf_counter
from typing import TypedDict


def model_registry(environ=None):
    """Return configured models without storing credential values in metadata."""
    env = os.environ if environ is None else environ
    models = []
    if env.get('ANTHROPIC_API_KEY'):
        for model in env.get('ANTHROPIC_EVAL_MODELS', env.get('ANTHROPIC_MODEL', '')).split(','):
            if model.strip():
                models.append(dict(name='anthropic/' + model.strip(), provider='anthropic', model=model.strip()))
    for provider in ('OPENAI', 'GROQ', 'NVIDIA', 'ZAI', 'DASHSCOPE', 'DEEPSEEK', 'MOONSHOT', 'OPENROUTER'):
        if not env.get(provider + '_API_KEY') or not env.get(provider + '_MODEL'):
            continue
        url = env.get(provider + '_BASE_URL') or None
        if provider != 'OPENAI' and not url:
            raise ValueError(provider + '_BASE_URL is required; refusing to route its key to a default provider')
        if url and not url.startswith('https://'):
            raise ValueError(provider + '_BASE_URL must use HTTPS')
        models.append(dict(name=provider.lower() + '/' + env[provider + '_MODEL'],
                           provider='openai_compat', model=env[provider + '_MODEL'],
                           key_env=provider + '_API_KEY', base_url=url))
    # An Ollama endpoint is not necessarily OpenAI-compatible; an explicit adapter
    # is needed before enabling the commented local-model settings from George's template.
    return models


def extract_cypher(text):
    if not isinstance(text, str):
        raise ValueError("Expected text model output")
    match = re.fullmatch(r"\s*```(?:cypher)?\s*(.*?)```\s*", text, re.S | re.I)
    return (match.group(1) if match else text).strip().removesuffix(";").strip()


def guard_query(query):
    """Conservative prefilter, NOT a database authorization boundary.

    Reject comments, escaped identifiers, all procedures, multiple statements,
    and write clauses. This deliberately rejects some valid read queries.
    Live execution additionally requires a server-enforced read-only DB user.
    """
    if not query or len(query) > 20000:
        raise ValueError("Missing or oversized query")
    if any(token in query for token in (";", "//", "/*", "*/", "`")):
        raise ValueError("Comments, escaped identifiers and multiple statements are unsupported")
    if re.search(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL|LOAD|FOREACH|INSERT|ALTER|GRANT|DENY|REVOKE|USE)\b", query, re.I):
        raise ValueError("Write, administration or procedure clause rejected")
    if not re.match(r"^(MATCH|OPTIONAL\s+MATCH|WITH|UNWIND|RETURN)\b", query, re.I):
        raise ValueError("Expected a read query")
    if not re.search(r"\bRETURN\b", query, re.I):
        raise ValueError("A result-returning query is required")


class State(TypedDict, total=False):
    qid: str
    question: str
    gold_cypher: str
    cypher: str
    error: str | None
    retries: int
    rows: list
    gold_rows: list
    match: bool
    generation_s: float
    raw: str


def build_graph(llm, run_cypher, schema):
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import SystemMessage, HumanMessage

    def generate(st):
        prompt = st['question']
        if st.get('error'):
            # Do not feed raw provider/DB errors (which may include credentials) back.
            prompt += '\nThe previous query failed validation or execution. Return a corrected read-only query.'
        start = perf_counter()
        try:
            response = llm.invoke([
                SystemMessage(content='Translate the question into one read-only Cypher query. '
                    'Use only this schema. Return a cypher code block.\n' + schema),
                HumanMessage(content=prompt)])
            text = response.content
            if isinstance(text, list):
                text = '\n'.join(b['text'] for b in text if isinstance(b, dict) and b.get('type') == 'text')
            return dict(raw=text, cypher=extract_cypher(text), error=None, rows=[],
                        generation_s=st.get('generation_s', 0) + perf_counter() - start)
        except Exception as exc:
            return dict(cypher='', rows=[], error='generation:' + type(exc).__name__,
                        generation_s=st.get('generation_s', 0) + perf_counter() - start)

    def guard(st):
        if st.get('error'):
            return {}
        try:
            guard_query(st['cypher'])
            return dict(error=None)
        except ValueError:
            return dict(error='guard:rejected', rows=[])

    def execute(st):
        try:
            return dict(rows=run_cypher(st['cypher']), error=None)
        except Exception as exc:
            return dict(rows=[], error='execution:' + type(exc).__name__)

    def compare(st):
        if st.get('error'):
            return dict(match=False, gold_rows=[])
        try:
            gold = run_cypher(st['gold_cypher'])
            norm = lambda rows: sorted(json.dumps(row, sort_keys=True, default=str) for row in rows)
            return dict(gold_rows=gold, match=norm(st['rows']) == norm(gold))
        except Exception as exc:
            return dict(match=False, error='reference:' + type(exc).__name__)

    def route(st):
        return 'retry' if st.get('error') and st.get('retries', 0) < 1 else ('compare' if st.get('error') else 'execute')

    def after_execute(st):
        return 'retry' if st.get('error') and st.get('retries', 0) < 1 else 'compare'

    graph = StateGraph(State)
    for name, node in [('generate', generate), ('guard', guard), ('execute', execute), ('compare', compare),
                       ('retry', lambda st: dict(retries=st.get('retries', 0) + 1))]:
        graph.add_node(name, node)
    graph.set_entry_point('generate')
    graph.add_edge('generate', 'guard')
    graph.add_conditional_edges('guard', route, {n: n for n in ('retry', 'compare', 'execute')})
    graph.add_conditional_edges('execute', after_execute, {n: n for n in ('retry', 'compare')})
    graph.add_edge('retry', 'generate')
    graph.add_edge('compare', END)
    return graph.compile()


def read_executor(driver, database, timeout=20, max_rows=10000):
    """Read routing is defense in depth; provision an actual read-only user."""
    from neo4j import Query, READ_ACCESS

    def run(query):
        guard_query(query)
        with driver.session(database=database, default_access_mode=READ_ACCESS) as session:
            result = session.run(Query(query, timeout=timeout))
            rows = []
            for record in result:
                if len(rows) >= max_rows:
                    raise ValueError('Result row limit exceeded')
                rows.append(dict(record))
            return rows
    return run
