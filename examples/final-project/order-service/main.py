# order-service/main.py
# 주문 서비스 — FastAPI + OpenTelemetry 계측
#
# - 주문 생성/조회 API
# - Inventory Service 호출 (분산 추적)
# - 수동 Span + 비즈니스 메트릭

import os
import sys
import time
import uuid
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 공유 모듈 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from opentelemetry import trace, metrics
from opentelemetry.trace import StatusCode, SpanKind
from opentelemetry.propagate import inject
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from shared.telemetry import init_telemetry


# --- OTel 초기화 ---
tracer_provider = None
meter_provider = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tracer_provider, meter_provider
    tracer_provider, meter_provider = init_telemetry("order-service", "1.0.0")
    yield
    if tracer_provider:
        tracer_provider.shutdown()
    if meter_provider:
        meter_provider.shutdown()


app = FastAPI(title="Order Service", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)

# trace.get_tracer() / metrics.get_meter()는 프록시 객체를 반환합니다.
# lifespan에서 init_telemetry()로 글로벌 Provider가 설정되면
# 프록시가 실제 Provider로 위임하므로 모듈 레벨에서 안전하게 생성 가능합니다.
tracer = trace.get_tracer("order-service")
meter = metrics.get_meter("order-service")

# 비즈니스 메트릭
order_counter = meter.create_counter(
    "orders.created.count",
    description="생성된 주문 수",
)
order_amount = meter.create_histogram(
    "orders.total.amount",
    description="주문 총액 분포",
    unit="KRW",
)

# 인메모리 데이터
orders_db: dict[str, dict] = {}

INVENTORY_SERVICE_URL = os.environ.get(
    "INVENTORY_SERVICE_URL", "http://inventory-service:8002"
)


# --- 모델 ---
class OrderItem(BaseModel):
    product_id: str
    quantity: int


class CreateOrderRequest(BaseModel):
    user_id: str
    items: list[OrderItem]


# --- API 엔드포인트 ---

@app.get("/orders")
async def list_orders():
    with tracer.start_as_current_span("list-orders") as span:
        span.set_attribute("orders.count", len(orders_db))
        return {"orders": list(orders_db.values())}


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    with tracer.start_as_current_span("get-order") as span:
        span.set_attribute("order.id", order_id)
        order = orders_db.get(order_id)
        if not order:
            span.set_status(StatusCode.ERROR, "주문 없음")
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다")
        return order


@app.post("/orders", status_code=201)
async def create_order(req: CreateOrderRequest):
    start_time = time.time()

    with tracer.start_as_current_span("create-order") as span:
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.user_id", req.user_id)
        span.set_attribute("order.item_count", len(req.items))

        # 재고 확인 (Inventory Service 호출)
        total_amount = 0
        order_items = []

        for item in req.items:
            inventory = await check_inventory(item.product_id, item.quantity)
            if not inventory.get("available"):
                span.set_status(StatusCode.ERROR, f"{item.product_id} 재고 부족")
                raise HTTPException(
                    status_code=400,
                    detail=f"{item.product_id} 재고가 부족합니다",
                )
            item_total = inventory["price"] * item.quantity
            total_amount += item_total
            order_items.append({
                "product_id": item.product_id,
                "quantity": item.quantity,
                "price": inventory["price"],
                "subtotal": item_total,
            })

        # 주문 저장
        with tracer.start_as_current_span("save-order") as save_span:
            order = {
                "order_id": order_id,
                "user_id": req.user_id,
                "items": order_items,
                "total_amount": total_amount,
                "status": "created",
            }
            orders_db[order_id] = order
            save_span.set_attribute("order.total_amount", total_amount)
            save_span.add_event("order.saved")

        # 메트릭 기록
        order_counter.add(1, {"status": "success"})
        order_amount.record(total_amount)

        duration_ms = (time.time() - start_time) * 1000
        span.set_attribute("order.processing_time_ms", round(duration_ms, 2))

        return order


async def check_inventory(product_id: str, quantity: int) -> dict:
    """Inventory Service에 재고 확인 요청"""
    with tracer.start_as_current_span(
        f"check-inventory/{product_id}",
        kind=SpanKind.CLIENT,
    ) as span:
        span.set_attribute("inventory.product_id", product_id)
        span.set_attribute("inventory.requested_quantity", quantity)

        # Context 전파: 현재 Trace 정보를 HTTP 헤더에 주입
        headers = {}
        inject(headers)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{INVENTORY_SERVICE_URL}/inventory/{product_id}",
                    headers=headers,
                    params={"quantity": quantity},
                    timeout=5.0,
                )
                response.raise_for_status()
                data = response.json()
                span.set_attribute("inventory.available", data.get("available", False))
                return data

        except httpx.HTTPStatusError as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise HTTPException(status_code=502, detail="재고 서비스 오류")
        except httpx.ConnectError as e:
            span.set_status(StatusCode.ERROR, "재고 서비스 연결 실패")
            span.record_exception(e)
            raise HTTPException(status_code=503, detail="재고 서비스에 연결할 수 없습니다")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "order-service"}
