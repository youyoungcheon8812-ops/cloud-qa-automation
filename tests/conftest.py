"""공통 fixture: 테스트용 서버 기동, API 클라이언트, 테스트 간 상태 초기화."""
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app.main import app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url() -> str:
    """세션 동안 실제 HTTP 서버를 백그라운드로 띄운다 (API·UI 테스트 공용)."""
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(f"{url}/api/instances", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.1)
    yield url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def api(base_url):
    with httpx.Client(base_url=base_url, timeout=5) as client:
        yield client


@pytest.fixture(autouse=True)
def reset_state(base_url):
    """각 테스트를 독립적으로 만들기 위해 매번 데이터를 비운다."""
    httpx.post(f"{base_url}/api/_reset")
    yield
