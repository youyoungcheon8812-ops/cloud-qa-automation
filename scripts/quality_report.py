"""JUnit XML·커버리지 XML을 읽어 품질 지표를 계산하고 Markdown/JSON으로 출력한다.

사용법:
    python scripts/quality_report.py reports/            # reports/ 아래 *.junit.xml, coverage.xml 사용
    python scripts/quality_report.py reports/ --summary $GITHUB_STEP_SUMMARY

지표
- 스위트별 테스트 수 / 통과 / 실패 / 스킵 / 통과율 / 실행 시간
- 가장 느린 테스트 Top 5 (느린 테스트는 flaky 원인이 되기 쉬움)
- 코드 커버리지 (라인 기준)
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET  # noqa: S405 - 신뢰된 CI 산출물만 파싱
from pathlib import Path


def parse_junit(path: Path) -> dict:
    root = ET.parse(path).getroot()  # noqa: S314
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    cases = []
    for s in suites:
        for c in s.findall("testcase"):
            if c.find("failure") is not None or c.find("error") is not None:
                status = "failed"
            elif c.find("skipped") is not None:
                status = "skipped"
            else:
                status = "passed"
            cases.append({"name": f"{c.get('classname', '')}::{c.get('name')}", "time": float(c.get("time", 0)),
                          "status": status})
    total = len(cases)
    passed = sum(c["status"] == "passed" for c in cases)
    failed = sum(c["status"] == "failed" for c in cases)
    skipped = sum(c["status"] == "skipped" for c in cases)
    executed = total - skipped
    return {
        "suite": path.name.removesuffix(".junit.xml"),
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": round(passed / executed * 100, 1) if executed else 0.0,
        "duration_sec": round(sum(c["time"] for c in cases), 2),
        "cases": cases,
    }


def parse_coverage(path: Path) -> float | None:
    if not path.exists():
        return None
    root = ET.parse(path).getroot()  # noqa: S314
    return round(float(root.get("line-rate", 0)) * 100, 1)


def build(report_dir: Path) -> dict:
    suites = [parse_junit(p) for p in sorted(report_dir.glob("*.junit.xml"))]
    all_cases = [c for s in suites for c in s["cases"]]
    executed = [c for c in all_cases if c["status"] != "skipped"]
    passed = sum(c["status"] == "passed" for c in executed)
    return {
        "suites": [{k: v for k, v in s.items() if k != "cases"} for s in suites],
        "total": len(all_cases),
        "passed": passed,
        "failed": sum(c["status"] == "failed" for c in all_cases),
        "pass_rate": round(passed / len(executed) * 100, 1) if executed else 0.0,
        "duration_sec": round(sum(c["time"] for c in all_cases), 2),
        "coverage_pct": parse_coverage(report_dir / "coverage.xml"),
        "slowest": sorted(all_cases, key=lambda c: c["time"], reverse=True)[:5],
    }


def to_markdown(m: dict) -> str:
    status = "✅ 통과" if m["failed"] == 0 else f"❌ 실패 {m['failed']}건"
    cov = f"{m['coverage_pct']}%" if m["coverage_pct"] is not None else "-"
    lines = [
        "## 품질 지표",
        "",
        "| 결과 | 테스트 수 | 통과율 | 실행 시간 | 코드 커버리지 |",
        "|---|---|---|---|---|",
        f"| {status} | {m['total']} | {m['pass_rate']}% | {m['duration_sec']}s | {cov} |",
        "",
        "### 스위트별",
        "| 스위트 | 테스트 | 통과 | 실패 | 스킵 | 통과율 | 시간 |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in m["suites"]:
        lines.append(f"| {s['suite']} | {s['total']} | {s['passed']} | {s['failed']} | {s['skipped']} "
                     f"| {s['pass_rate']}% | {s['duration_sec']}s |")
    lines += ["", "### 가장 느린 테스트 Top 5", "| 테스트 | 시간 |", "|---|---|"]
    for c in m["slowest"]:
        lines.append(f"| `{c['name']}` | {c['time']:.2f}s |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report_dir", type=Path)
    ap.add_argument("--summary", type=Path, help="Markdown을 덧붙일 파일 (예: $GITHUB_STEP_SUMMARY)")
    ap.add_argument("--min-pass-rate", type=float, default=100.0)
    ap.add_argument("--min-coverage", type=float, default=0.0)
    args = ap.parse_args()

    metrics = build(args.report_dir)
    md = to_markdown(metrics)
    print(md)
    (args.report_dir / "quality.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as f:
            f.write(md)

    # 품질 게이트: 기준 미달이면 CI 실패
    if metrics["pass_rate"] < args.min_pass_rate:
        print(f"품질 게이트 실패: 통과율 {metrics['pass_rate']}% < {args.min_pass_rate}%", file=sys.stderr)
        return 1
    if metrics["coverage_pct"] is not None and metrics["coverage_pct"] < args.min_coverage:
        print(f"품질 게이트 실패: 커버리지 {metrics['coverage_pct']}% < {args.min_coverage}%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
