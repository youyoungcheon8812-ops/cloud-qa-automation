"""웹 콘솔 UI 테스트 (Playwright): 사용자가 실제로 클릭하는 흐름 검증."""
import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.ui


@pytest.fixture
def console(page: Page, base_url) -> Page:
    page.goto(base_url)
    expect(page.get_by_role("heading", name="Mini Cloud Console")).to_be_visible()
    return page


def create_via_ui(page: Page, name: str, flavor: str = "m2.c1m2"):
    page.get_by_label("인스턴스 이름").fill(name)
    page.get_by_label("인스턴스 타입").select_option(flavor)
    page.get_by_role("button", name="생성").click()


def test_empty_state_message(console: Page):
    expect(console.locator("#empty")).to_be_visible()


def test_create_instance_shows_in_table(console: Page):
    create_via_ui(console, "web-01", "m2.c2m4")
    row = console.locator("tr[data-name='web-01']")
    expect(row).to_be_visible()
    expect(row).to_contain_text("m2.c2m4")
    expect(row.get_by_test_id("status")).to_have_text("RUNNING")
    expect(console.locator("#empty")).to_be_hidden()


def test_invalid_name_shows_error(console: Page):
    create_via_ui(console, "Web_01")
    expect(console.locator("#create-error")).to_contain_text("영문 소문자")
    expect(console.locator("tbody tr")).to_have_count(0)


def test_duplicate_name_shows_error(console: Page):
    create_via_ui(console, "dup")
    # 첫 생성이 끝나 목록에 나타날 때까지 기다린 뒤 두 번째 생성 (CI에서 발견한 race condition 대응)
    expect(console.locator("tr[data-name='dup']")).to_be_visible()
    create_via_ui(console, "dup")
    expect(console.locator("#create-error")).to_contain_text("이미 있습니다")
    expect(console.locator("tbody tr")).to_have_count(1)


def test_stop_and_start_toggle(console: Page):
    create_via_ui(console, "web-01")
    row = console.locator("tr[data-name='web-01']")
    row.get_by_role("button", name="정지").click()
    expect(row.get_by_test_id("status")).to_have_text("STOPPED")
    row.get_by_role("button", name="시작").click()
    expect(row.get_by_test_id("status")).to_have_text("RUNNING")


def test_delete_removes_row(console: Page):
    create_via_ui(console, "web-01")
    console.locator("tr[data-name='web-01']").get_by_role("button", name="삭제").click()
    expect(console.locator("tr[data-name='web-01']")).to_have_count(0)
    expect(console.locator("#empty")).to_be_visible()


@pytest.mark.parametrize("hours, expected", [("10", "0원"), ("20", "1,200원"), ("744", "88,080원")])
def test_billing_calculator(console: Page, hours, expected):
    console.get_by_label("요금 계산 타입").select_option("m2.c4m8")
    console.get_by_label("사용 시간").fill(hours)
    console.get_by_role("button", name="계산").click()
    expect(console.get_by_test_id("bill-result")).to_contain_text(expected)


def test_billing_out_of_range_shows_error(console: Page):
    console.get_by_label("사용 시간").fill("745")
    console.get_by_role("button", name="계산").click()
    expect(console.locator("#bill-error")).to_contain_text("0~744")
    expect(console.get_by_test_id("bill-result")).to_have_text("")
