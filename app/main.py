"""
Mini Cloud Console — 테스트 대상(SUT)으로 쓰는 작은 클라우드 콘솔 서비스.

실제 클라우드 콘솔의 핵심 흐름을 단순화해 구현했다.
- 인스턴스: 생성 / 조회 / 정지 / 시작 / 삭제
- 빌링: 사용 시간 기반 월 요금 계산 (무료 사용량, 최대 시간 경계 포함)
- 웹 콘솔: / 경로의 HTML 화면 (Playwright UI 테스트 대상)
"""
from __future__ import annotations

import re
import uuid
from enum import StrEnum
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Mini Cloud Console")

# 인스턴스 타입별 시간당 요금(원)
FLAVORS: dict[str, int] = {"m2.c1m2": 30, "m2.c2m4": 60, "m2.c4m8": 120, "g2.a100": 2500}
FREE_HOURS = 10          # 월 무료 사용 시간
MAX_HOURS = 744          # 31일 * 24시간
NAME_PATTERN = re.compile(r"^[a-z0-9-]{1,32}$")


class Status(StrEnum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"


class InstanceCreate(BaseModel):
    name: str
    flavor: str

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        if not NAME_PATTERN.match(v):
            raise ValueError("이름은 영문 소문자·숫자·하이픈 1~32자여야 합니다.")
        return v

    @field_validator("flavor")
    @classmethod
    def check_flavor(cls, v: str) -> str:
        if v not in FLAVORS:
            raise ValueError(f"지원하지 않는 인스턴스 타입입니다: {v}")
        return v


class Instance(BaseModel):
    id: str
    name: str
    flavor: str
    status: Status


class BillingRequest(BaseModel):
    flavor: str
    hours: float = Field(ge=0, le=MAX_HOURS)


_instances: dict[str, Instance] = {}


@app.post("/api/instances", status_code=201, response_model=Instance)
def create_instance(body: InstanceCreate) -> Instance:
    if any(i.name == body.name for i in _instances.values()):
        raise HTTPException(409, "같은 이름의 인스턴스가 이미 있습니다.")
    inst = Instance(id=uuid.uuid4().hex[:8], name=body.name, flavor=body.flavor, status=Status.RUNNING)
    _instances[inst.id] = inst
    return inst


@app.get("/api/instances", response_model=list[Instance])
def list_instances() -> list[Instance]:
    return list(_instances.values())


@app.get("/api/instances/{instance_id}", response_model=Instance)
def get_instance(instance_id: str) -> Instance:
    if instance_id not in _instances:
        raise HTTPException(404, "인스턴스를 찾을 수 없습니다.")
    return _instances[instance_id]


@app.post("/api/instances/{instance_id}/{action}", response_model=Instance)
def change_state(instance_id: str, action: str) -> Instance:
    inst = get_instance(instance_id)
    if action == "stop":
        if inst.status == Status.STOPPED:
            raise HTTPException(409, "이미 정지된 인스턴스입니다.")
        inst.status = Status.STOPPED
    elif action == "start":
        if inst.status == Status.RUNNING:
            raise HTTPException(409, "이미 실행 중인 인스턴스입니다.")
        inst.status = Status.RUNNING
    else:
        raise HTTPException(400, f"지원하지 않는 동작입니다: {action}")
    return inst


@app.delete("/api/instances/{instance_id}", status_code=204)
def delete_instance(instance_id: str) -> Response:
    get_instance(instance_id)
    del _instances[instance_id]
    return Response(status_code=204)


@app.post("/api/billing/estimate")
def estimate(body: BillingRequest) -> dict:
    if body.flavor not in FLAVORS:
        raise HTTPException(422, f"지원하지 않는 인스턴스 타입입니다: {body.flavor}")
    billable = max(0.0, body.hours - FREE_HOURS)
    # 과금은 1시간 단위 올림
    billable_hours = int(-(-billable // 1))
    return {
        "flavor": body.flavor,
        "hours": body.hours,
        "free_hours": FREE_HOURS,
        "billable_hours": billable_hours,
        "amount": billable_hours * FLAVORS[body.flavor],
        "currency": "KRW",
    }


@app.post("/api/_reset", include_in_schema=False)
def reset() -> dict:
    """테스트 격리를 위한 상태 초기화."""
    _instances.clear()
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def console() -> str:
    return (Path(__file__).parent / "console.html").read_text(encoding="utf-8")
