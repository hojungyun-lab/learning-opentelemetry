# inventory-service/main.py
# 재고 서비스 — FastAPI + OpenTelemetry 계측
#
# - 재고 조회/확인 API
# - 수신된 Context에서 Trace 연결 (분산 추적)

import os
import sys
import time
import random
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query

# 공유 모듈 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opentelemetry import trace, metrics
from opentelemetry.trace import StatusCode
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from shared.telemetry import init_telemetry

# --- OTel 초기화 ---
tracer_provider = None
meter_provider = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tracer_provider, meter_provider
    tracer_provider, meter_provider = init_telemetry("inventory-service", "1.0.0")
    yield
    if tracer_provider:
        tracer_provider.shutdown()
    if meter_provider:
        meter_provider.shutdown()


app = FastAPI(title="Inventory Service", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)

# trace.get_tracer() / metrics.get_meter()는 프록시 객체를 반환합니다.
# lifespan에서 init_telemetry()로 글로벌 Provider가 설정되면
# 프록시가 실제 Provider로 위임하므로 모듈 레벨에서 안전하게 생성 가능합니다.
tracer = trace.get_tracer("inventory-service")
meter = metrics.get_meter("inventory-service")

# 메트릭
inventory_check_counter = meter.create_counter(
    "inventory.check.count",
    description="재고 확인 요청 수",
)

# 인메모리 재고 데이터
inventory_db = {
    "PROD-001": {"product_id": "PROD-001", "name": "노트북", "price": 1200000, "stock": 50},
    "PROD-002": {"product_id": "PROD-002", "name": "키보드", "price": 85000, "stock": 200},
    "PROD-003": {"product_id": "PROD-003", "name": "모니터", "price": 350000, "stock": 30},
    "PROD-004": {"product_id": "PROD-004", "name": "마우스", "price": 45000, "stock": 150},
    "PROD-005": {"product_id": "PROD-005", "name": "헤드셋", "price": 120000, "stock": 0},
}


# --- API 엔드포인트 ---

@app.get("/inventory")
async def list_inventory():
    """전체 재고 목록 조회"""
    with tracer.start_as_current_span("list-inventory") as span:
        span.set_attribute("inventory.product_count", len(inventory_db))
        return {"inventory": list(inventory_db.values())}


@app.get("/inventory/{product_id}")
async def check_inventory(product_id: str, quantity: int = Query(default=1)):
    """
    재고 확인 및 가용성 반환.
    FastAPI 자동 계측이 SERVER Span을 생성하고,
    Order Service에서 전파된 Trace Context를 자동으로 연결합니다.
    """
    with tracer.start_as_current_span("check-stock") as span:
        span.set_attribute("product.id", product_id)
        span.set_attribute("requested.quantity", quantity)

        product = inventory_db.get(product_id)
        if not product:
            span.set_status(StatusCode.ERROR, f"상품 {product_id} 없음")
            inventory_check_counter.add(1, {
                "product_id": product_id,
                "result": "not_found",
            })
            return {"product_id": product_id, "available": False, "reason": "상품 없음"}

        # DB 조회 시뮬레이션
        with tracer.start_as_current_span("db.query") as db_span:
            db_span.set_attribute("db.system", "postgresql")
            db_span.set_attribute("db.operation.name", "SELECT")
            time.sleep(random.uniform(0.005, 0.02))

        available = product["stock"] >= quantity
        span.set_attribute("product.stock", product["stock"])
        span.set_attribute("product.available", available)

        result = "available" if available else "insufficient"
        inventory_check_counter.add(1, {
            "product_id": product_id,
            "result": result,
        })

        if available:
            span.add_event("stock.sufficient", {
                "current_stock": product["stock"],
                "requested": quantity,
            })
        else:
            span.add_event("stock.insufficient", {
                "current_stock": product["stock"],
                "requested": quantity,
            })

        return {
            "product_id": product_id,
            "name": product["name"],
            "price": product["price"],
            "stock": product["stock"],
            "available": available,
            "requested_quantity": quantity,
        }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "inventory-service"}
