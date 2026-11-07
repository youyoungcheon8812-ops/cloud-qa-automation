"""빌링(요금 계산) API 테스트.

요금 규칙
- 월 무료 사용 10시간
- 무료 사용량 초과분은 1시간 단위 올림 과금
- 사용 시간 허용 범위: 0 ~ 744시간 (31일)

경계값: 0 / 10 / 10.1 / 11 / 744 / 744.1 / -1
"""
import pytest

pytestmark = pytest.mark.api

PRICE = {"m2.c1m2": 30, "m2.c2m4": 60, "m2.c4m8": 120, "g2.a100": 2500}


def estimate(api, hours, flavor="m2.c2m4"):
    return api.post("/api/billing/estimate", json={"flavor": flavor, "hours": hours})


@pytest.mark.parametrize(
    "hours, billable",
    [
        (0, 0),        # 최소값
        (9.9, 0),      # 무료 구간 내부
        (10, 0),       # 무료 구간 경계
        (10.1, 1),     # 무료 초과 직후 → 1시간 올림
        (11, 1),
        (744, 734),    # 최대값
    ],
)
def test_billable_hours_boundaries(api, hours, billable):
    r = estimate(api, hours)
    assert r.status_code == 200
    body = r.json()
    assert body["billable_hours"] == billable
    assert body["amount"] == billable * PRICE["m2.c2m4"]


@pytest.mark.parametrize("hours", [-1, -0.1, 744.1, 1000])
def test_out_of_range_hours_rejected(api, hours):
    assert estimate(api, hours).status_code == 422


@pytest.mark.parametrize("flavor, price", PRICE.items())
def test_amount_per_flavor(api, flavor, price):
    # 동등 분할: 타입별로 대표값 하나씩 (20시간 → 과금 10시간)
    assert estimate(api, 20, flavor).json()["amount"] == 10 * price


def test_unknown_flavor_rejected(api):
    assert estimate(api, 20, "x9.huge").status_code == 422


def test_response_schema(api):
    body = estimate(api, 20).json()
    assert set(body) == {"flavor", "hours", "free_hours", "billable_hours", "amount", "currency"}
    assert body["currency"] == "KRW"
    assert isinstance(body["amount"], int)
