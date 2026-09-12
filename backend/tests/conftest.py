import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.ai as ai_module
import app.db.session as db_session_module
import app.storage as storage_module
from app.ai.base import AIProvider, AIProviderError
from app.api.routes.ai import get_provider
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _isolate_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    storage_module.get_storage.cache_clear()
    yield
    storage_module.get_storage.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_background_task_sessions(monkeypatch):
    # BackgroundTasks (e.g. analytics recalculation) open their own session via
    # app.db.session.SessionLocal rather than the request-scoped get_db override --
    # point that at the same in-memory test engine or they'd hit the real database.
    monkeypatch.setattr(db_session_module, "SessionLocal", TestingSessionLocal)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class FakeAIProvider(AIProvider):
    """Test double -- no real API calls happen in the suite. Configure
    `structured_response` / `text_responses` per test; both raise
    AIProviderError if `should_error` is set, so error-handling paths are
    exercisable without a real provider failure.
    """

    def __init__(self):
        self.structured_response: dict | None = None
        self.text_responses: list[str] = []
        self.should_error: bool = False
        self.calls: list[str] = []

    def generate_structured(self, prompt: str, json_schema: dict, tool_name: str) -> dict:
        self.calls.append(prompt)
        if self.should_error:
            raise AIProviderError("fake provider error")
        return self.structured_response

    def generate_text(self, prompt: str, max_tokens: int = 1024) -> str:
        self.calls.append(prompt)
        if self.should_error:
            raise AIProviderError("fake provider error")
        if len(self.text_responses) > 1:
            return self.text_responses.pop(0)
        return self.text_responses[0] if self.text_responses else ""


@pytest.fixture
def fake_ai_provider(monkeypatch):
    provider = FakeAIProvider()
    monkeypatch.setattr(ai_module, "get_ai_provider", lambda: provider)
    app.dependency_overrides[get_provider] = lambda: provider
    yield provider
    del app.dependency_overrides[get_provider]


def register(client: TestClient, name: str, email: str, password: str = "password123", role: str = "STUDENT") -> dict:
    response = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password, "role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
