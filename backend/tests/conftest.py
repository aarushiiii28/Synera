"""API test setup: temporary application database, temporary ledger, tiny pipeline dataset."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="synera_api_test_")
os.environ["SYNERA_DB_PATH"] = os.path.join(_TMP, "test.db")   # must be set before the backend is imported

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tests.conftest import make_panel, tiny_registry, tmp_ledger  # noqa: E402,F401  (re-exported fixtures)


@pytest.fixture()
def client(tmp_ledger, monkeypatch):  # noqa: F811  (fixture parameter shadows the re-exported fixture by design)
    from backend.app import main
    from backend.app.core.deps import get_ledger
    from backend.app.db.database import engine
    from backend.app.db.models import SQLModel

    SQLModel.metadata.drop_all(engine)
    monkeypatch.setattr(main, "get_ledger", lambda: tmp_ledger)
    main.app.dependency_overrides[get_ledger] = lambda: tmp_ledger
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()
