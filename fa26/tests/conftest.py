import pytest


def _rec(title, description="", sectors=()):
    """Minimal activity record in the shape parse_activity() returns,
    with only the fields hunger_match() reads."""
    return {
        "activity": {"title": title, "description": description},
        "sectors": [{"code": c, "vocabulary": v, "name": n, "percentage": ""}
                    for c, v, n in sectors],
        "transactions": [],
    }


@pytest.fixture
def make_rec():
    return _rec
