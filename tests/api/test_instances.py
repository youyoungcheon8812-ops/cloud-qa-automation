"""인스턴스 API 테스트: 정상 흐름, 입력 검증(동등 분할·경계값), 상태 전이, 오류 응답."""
import pytest

pytestmark = pytest.mark.api


def create(api, name="web-01", flavor="m2.c1m2"):
    return api.post("/api/instances", json={"name": name, "flavor": flavor})


class TestCreate:
    def test_create_returns_201_and_running(self, api):
        r = create(api)
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "web-01"
        assert body["status"] == "RUNNING"
        assert len(body["id"]) == 8

    def test_created_instance_appears_in_list(self, api):
        created = create(api).json()
        ids = [i["id"] for i in api.get("/api/instances").json()]
        assert created["id"] in ids

    @pytest.mark.parametrize("name", ["a", "a" * 32, "web-01", "0-0"])
    def test_valid_name_boundaries(self, api, name):
        # 경계값: 최소 1자, 최대 32자 / 허용 문자 조합
        assert create(api, name=name).status_code == 201

    @pytest.mark.parametrize(
        "name, reason",
        [
            ("", "빈 문자열 (최소 길이 미만)"),
            ("a" * 33, "33자 (최대 길이 초과)"),
            ("Web-01", "대문자 포함"),
            ("web_01", "허용되지 않은 특수문자"),
            ("웹서버", "한글"),
        ],
    )
    def test_invalid_name_rejected(self, api, name, reason):
        r = create(api, name=name)
        assert r.status_code == 422, reason

    def test_unknown_flavor_rejected(self, api):
        assert create(api, flavor="x9.huge").status_code == 422

    def test_duplicate_name_conflict(self, api):
        create(api, name="dup")
        r = create(api, name="dup")
        assert r.status_code == 409


class TestStateTransition:
    def test_stop_then_start(self, api):
        iid = create(api).json()["id"]
        assert api.post(f"/api/instances/{iid}/stop").json()["status"] == "STOPPED"
        assert api.post(f"/api/instances/{iid}/start").json()["status"] == "RUNNING"

    def test_stop_twice_conflict(self, api):
        iid = create(api).json()["id"]
        api.post(f"/api/instances/{iid}/stop")
        assert api.post(f"/api/instances/{iid}/stop").status_code == 409

    def test_start_running_conflict(self, api):
        iid = create(api).json()["id"]
        assert api.post(f"/api/instances/{iid}/start").status_code == 409

    def test_unknown_action_bad_request(self, api):
        iid = create(api).json()["id"]
        assert api.post(f"/api/instances/{iid}/reboot-now").status_code == 400


class TestDelete:
    def test_delete_then_get_404(self, api):
        iid = create(api).json()["id"]
        assert api.delete(f"/api/instances/{iid}").status_code == 204
        assert api.get(f"/api/instances/{iid}").status_code == 404

    def test_delete_unknown_404(self, api):
        assert api.delete("/api/instances/nothere").status_code == 404
