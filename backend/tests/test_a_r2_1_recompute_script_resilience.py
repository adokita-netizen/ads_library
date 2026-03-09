from sqlalchemy.exc import OperationalError

from scripts import recompute_hit_scores as recompute_mod


class _FailingQuery:
    def all(self):
        raise OperationalError("SELECT ...", {}, Exception("missing column"))


class _FakeSession:
    def __init__(self):
        self.rollback_called = 0
        self.commit_called = 0

    def query(self, _model):
        return _FailingQuery()

    def rollback(self):
        self.rollback_called += 1

    def commit(self):
        self.commit_called += 1


def test_sync_product_rankings_skips_schema_mismatch():
    session = _FakeSession()

    updated, error = recompute_mod._sync_product_rankings(session, [{"id": 1, "score": 50.0, "hit_level": "hit"}])

    assert updated == 0
    assert "missing column" in error
    assert session.rollback_called == 1
    assert session.commit_called == 0
