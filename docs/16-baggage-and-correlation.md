# 🧳 16. Baggage와 Correlation

## 학습 목표

Baggage API를 사용하여 서비스 간에 임의의 키-값 데이터를 전파하는 방법과, 세 가지 신호(Traces, Metrics, Logs) 간의 상관관계(Correlation)를 파악하는 방법을 학습합니다.

---

## 핵심 개념

### Baggage란?

Baggage는 **서비스 간에 전파되는 키-값 쌍**입니다. Trace Context와 함께 HTTP 헤더를 통해 자동으로 전달됩니다.

```
Service A                     Service B                     Service C
┌───────────────┐            ┌───────────────┐            ┌───────────────┐
│ Baggage:      │  ──HTTP──→ │ Baggage:      │  ──HTTP──→ │ Baggage:      │
│  user.id=42   │            │  user.id=42   │            │  user.id=42   │
│  tenant=acme  │            │  tenant=acme  │            │  tenant=acme  │
└───────────────┘            └───────────────┘            └───────────────┘
```

**Baggage vs. Span Attributes**:

| 항목 | Baggage | Span Attributes |
|------|---------|-----------------|
| 전파 범위 | 모든 다운스트림 서비스 | 해당 Span에만 기록 |
| 자동 기록 | 아니오 (명시적으로 읽어야 함) | 예 |
| 크기 제한 | 있음 (헤더 크기 제한) | 실질적으로 없음 |
| 용도 | 서비스 간 메타데이터 공유 | 개별 작업의 상세 정보 |

### 주의사항

Baggage는 **HTTP 헤더로 전달**되므로:
- 민감 정보(비밀번호, 토큰 등)를 넣으면 안 됩니다
- 크기를 작게 유지해야 합니다 (헤더 크기 제한)
- 모든 다운스트림 서비스에 전파되므로, 필요한 정보만 포함합니다

---

## 실습

### 1단계: Baggage 기본 사용

```python
# baggage_basic.py
# Baggage API 기본 사용법

from opentelemetry import baggage, context, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "baggage-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# --- Baggage 설정 ---

# baggage.set_baggage()는 새 Context를 반환 (기존 Context는 변경하지 않음)
ctx = baggage.set_baggage("user.id", "user-42")
ctx = baggage.set_baggage("tenant.id", "acme-corp", context=ctx)
ctx = baggage.set_baggage("request.priority", "high", context=ctx)

# Context를 활성화
token = context.attach(ctx)

# --- Baggage 조회 ---

# 개별 조회
user_id = baggage.get_baggage("user.id")
tenant_id = baggage.get_baggage("tenant.id")
print(f"User: {user_id}, Tenant: {tenant_id}")

# 전체 조회
all_baggage = baggage.get_all()
print(f"All Baggage: {all_baggage}")

# --- Baggage를 Span 속성으로 활용 ---

with tracer.start_as_current_span("process-request") as span:
    # Baggage 값을 Span 속성으로 복사
    # (Baggage는 자동으로 Span에 기록되지 않으므로 명시적으로 추가)
    for key, value in baggage.get_all().items():
        span.set_attribute(f"baggage.{key}", value)

    print("Baggage 값이 Span 속성으로 복사되었습니다.")

# Context 복원
context.detach(token)

# --- Baggage 제거 ---
ctx_without = baggage.remove_baggage("request.priority")
print(f"제거 후: {baggage.get_all(context=ctx_without)}")

provider.shutdown()
```

### 2단계: 서비스 간 Baggage 전파

```python
# baggage_propagation.py
# 서비스 간 Baggage 자동 전파

from opentelemetry import baggage, context, trace
from opentelemetry.propagate import inject, extract
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "baggage-propagation-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)


def api_gateway():
    """API Gateway: Baggage 설정 후 하위 서비스 호출"""
    # 요청에서 사용자 정보를 추출하여 Baggage에 설정
    ctx = baggage.set_baggage("user.id", "user-42")
    ctx = baggage.set_baggage("user.role", "premium")
    ctx = baggage.set_baggage("ab.test.group", "experiment-B")
    token = context.attach(ctx)

    with tracer.start_as_current_span("gateway-handler"):
        # HTTP 헤더에 Trace Context + Baggage를 주입
        headers = {}
        inject(headers)
        print(f"[Gateway] 전파할 헤더: {headers}")

        # 하위 서비스 호출 시뮬레이션
        order_service(headers)

    context.detach(token)


def order_service(incoming_headers: dict):
    """Order Service: Baggage를 수신하여 활용"""
    # 헤더에서 Context + Baggage 추출
    ctx = extract(carrier=incoming_headers)
    token = context.attach(ctx)

    with tracer.start_as_current_span("process-order") as span:
        # 전파된 Baggage 조회
        user_id = baggage.get_baggage("user.id")
        user_role = baggage.get_baggage("user.role")
        ab_group = baggage.get_baggage("ab.test.group")

        print(f"[Order] 수신된 Baggage:")
        print(f"  user.id: {user_id}")
        print(f"  user.role: {user_role}")
        print(f"  ab.test.group: {ab_group}")

        # Baggage 값을 Span 속성으로 활용
        span.set_attribute("user.id", user_id or "unknown")
        span.set_attribute("user.role", user_role or "unknown")

        # A/B 테스트 그룹에 따른 로직 분기
        if ab_group == "experiment-B":
            span.add_event("ab_test.new_checkout_flow")

    context.detach(token)


api_gateway()
provider.shutdown()
```

### 3단계: Baggage 활용 사례

```python
# 실전 사용 예시

# 1. 멀티 테넌트: 테넌트 ID를 모든 서비스에 전파
ctx = baggage.set_baggage("tenant.id", "acme-corp")

# 2. A/B 테스트: 실험 그룹 정보 전파
ctx = baggage.set_baggage("experiment.id", "checkout-v2")
ctx = baggage.set_baggage("experiment.variant", "B")

# 3. 요청 우선순위: 과금 등급에 따른 처리 우선순위
ctx = baggage.set_baggage("request.priority", "high")

# 4. 디버깅: 특정 요청에 대해 상세 로깅 활성화
ctx = baggage.set_baggage("debug.verbose", "true")
```

---

## Correlation: 세 신호 간의 연결

### Trace-Log Correlation

Span 내에서 생성된 로그는 자동으로 `trace_id`와 `span_id`가 첨부됩니다 (08장에서 학습).

```python
# Jaeger/Grafana에서 Trace를 보면서 해당 시점의 로그를 조회
# → trace_id로 검색하면 해당 요청의 모든 로그를 확인 가능
```

### Trace-Metric Correlation (Exemplars)

Exemplars를 통해 메트릭의 특정 데이터 포인트가 어떤 Trace에서 발생했는지 연결합니다 (07장에서 학습).

```
[Grafana] http_request_duration_p99 = 2.5s
    → Exemplar 클릭
    → trace_id: abc123...
    → [Jaeger] 해당 Trace 조회 → 결제 서비스에서 2.3s 소요 확인
```

### 전체 Correlation 흐름

```
1. [Metrics] 에러율 알람 발생 (error_rate > 5%)
2. [Metrics → Exemplars] 에러 Trace ID 확인
3. [Traces] 해당 Trace를 Jaeger에서 조회 → 결제 서비스에서 타임아웃 발생
4. [Traces → Logs] trace_id로 로그 검색 → "외부 결제 API 응답 없음" 로그 발견
5. [Root Cause] 외부 결제 API 장애 확인
```

---

## 마무리

이번 단계에서 학습한 것:

- **Baggage API**: `set_baggage()`, `get_baggage()`, `get_all()`을 통한 데이터 관리
- **서비스 간 전파**: `inject()`/`extract()`를 통한 Baggage 자동 전파
- **실전 활용**: 멀티 테넌트, A/B 테스트, 디버깅 모드
- **Correlation**: Traces ↔ Metrics ↔ Logs 간의 연결 관계

**다음 단계**: [17. 테스트와 디버깅](17-testing-and-debugging.md)에서 계측 코드를 테스트하고 문제를 진단하는 전략을 학습합니다.
