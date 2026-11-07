# Cloud QA Automation

![QA Automation](https://github.com/youyoungcheon8812-ops/cloud-qa-automation/actions/workflows/test.yml/badge.svg)

클라우드 콘솔의 핵심 기능(인스턴스 관리, 요금 계산)을 단순화한 **Mini Cloud Console**을 테스트 대상으로 두고,
**pytest 기반 API 테스트**와 **Playwright 기반 UI 테스트**를 작성해 **GitHub Actions**에서 자동 실행하는 QA 자동화 프로젝트입니다.

## 왜 만들었나
TMAP for Car QA 업무에서 업데이트마다 같은 회귀 테스트를 수동으로 반복하면서, 반복 검증은 자동화되어야 한다고 느꼈습니다.
클라우드 서비스의 콘솔·빌링처럼 **경계값 하나가 고객 요금에 직결되는 기능**을 대상으로, 테스트 설계부터 자동화·CI까지 직접 구성했습니다.

## 구성
```
app/                    테스트 대상 (FastAPI)
  main.py               인스턴스 API, 요금 계산 API
  console.html          웹 콘솔 화면
tests/
  conftest.py           테스트 서버 기동, 테스트 간 상태 초기화
  api/test_instances.py 인스턴스 API (생성·검증·상태 전이·삭제)
  api/test_billing.py   요금 계산 API (경계값·동등 분할·스키마)
  ui/test_console.py    웹 콘솔 사용자 흐름 (Playwright)
.github/workflows/      CI: API 테스트 → UI 테스트, HTML 리포트 업로드
```

## 테스트 설계

### 1. 요금 계산 — 경계값 분석
규칙: 월 무료 10시간, 초과분은 1시간 단위 올림 과금, 허용 범위 0~744시간

| 입력(시간) | 기대 과금 시간 | 의도 |
|---|---|---|
| 0 | 0 | 최소값 |
| 10 | 0 | 무료 구간 경계 |
| **10.1** | **1** | 무료 초과 직후 올림 처리 |
| 744 | 734 | 최대값 |
| -1, 744.1 | 422 오류 | 범위 밖 |

> 검증: 올림 처리를 내림으로 바꾸는 버그를 일부러 넣었을 때 `10.1시간` 케이스가 실패하는 것을 확인했습니다.

### 2. 인스턴스 이름 — 동등 분할 + 경계값
- 유효: 1자, 32자, 소문자·숫자·하이픈 조합
- 무효: 빈 문자열, 33자, 대문자, 언더스코어, 한글 → 422

### 3. 상태 전이
`RUNNING → stop → STOPPED → start → RUNNING`, 같은 상태로의 전이는 409, 지원하지 않는 동작은 400

### 4. UI 사용자 흐름 (Playwright)
생성 → 목록 표시, 입력 오류 메시지, 중복 이름 오류, 정지/시작 토글, 삭제, 요금 계산기 결과·오류

## 실행
```bash
pip install -r requirements.txt
python -m playwright install chromium

pytest -m api        # API 테스트 (35개)
pytest -m ui         # UI 테스트 (10개)
pytest --html=reports/report.html --self-contained-html   # 전체 + HTML 리포트
```

## CI
`main` push / PR마다 GitHub Actions가 API 테스트 → UI 테스트 순서로 실행합니다.
UI 테스트 실패 시 스크린샷과 Playwright trace가 아티팩트로 업로드되어 재현 근거로 사용할 수 있습니다.

## CI에서 발견한 문제와 해결
로컬에서는 45개 모두 통과했지만, 첫 CI 실행에서 `test_duplicate_name_shows_error`가 실패했습니다.

- **증상:** 중복 이름 오류(409) 대신 이름 형식 오류(422) 메시지가 표시됨
- **원인:** 첫 번째 생성 요청의 응답이 오기 전에 두 번째 이름을 입력했고, 뒤늦게 도착한 첫 응답이 입력칸을 비우면서 두 번째 요청에 빈 이름이 전송됨 (race condition)
- **로컬에서 통과한 이유:** 응답이 빨라 타이밍이 우연히 맞았음
- **해결:** 첫 인스턴스가 목록에 나타난 것을 확인한 뒤 두 번째 생성을 수행하도록 대기 조건 추가

> 실행 환경에 따라 결과가 달라지는 flaky 테스트는 "통과했다"는 사실보다 "왜 통과했는지"를 확인해야 한다는 점을 배웠습니다.

## 다음 단계
- [ ] 테스트 결과를 품질 지표(통과율, 실행 시간 추이)로 시각화
- [ ] SonarQube 정적 분석 연동
- [ ] Docker로 테스트 대상 서버를 컨테이너화
