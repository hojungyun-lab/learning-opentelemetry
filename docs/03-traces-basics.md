# 🔗 03. Traces 기초 (Traces Basics)

## 학습 목표

TracerProvider를 설정하고, Span을 생성하여 콘솔에 출력하는 기본 흐름을 익힙니다. Trace와 Span의 관계를 코드를 통해 이해합니다.

---

## 핵심 개념

### Trace와 Span

- **Trace**: 하나의 요청이 시스템을 통과하는 전체 경로를 나타냅니다. 고유한 `trace_id`로 식별됩니다.
- **Span**: Trace를 구성하는 개별 작업 단위입니다. 각 Span은 이름, 시작/종료 시각, 소속된 `trace_id`, 자신의 `span_id`를 가집니다.

하나의 Trace는 하나 이상의 Span으로 구성되며, Span 간에는 부모-자식 관계가 형성됩니다. 이 관계를 통해 요청의 흐름을 트리 구조로 시각화할 수 있습니다.

### Span의 구성 요소

| 필드 | 설명 | 예시 |
|------|------|------|
| `name` | 작업을 설명하는 이름 | `"GET /api/users"` |
| `trace_id` | 소속 Trace의 고유 ID (128비트) | `0x4bf92f...` |
| `span_id` | 이 Span의 고유 ID (64비트) | `0x00f067...` |
| `parent_span_id` | 부모 Span의 ID (루트 Span은 없음) | `0x00f067...` |
| `start_time` | 시작 시각 (나노초 정밀도) | - |
| `end_time` | 종료 시각 | - |
| `status` | 성공/에러 상태 | `OK`, `ERROR` |
| `kind` | Span의 유형 | `SERVER`, `CLIENT`, `INTERNAL` |
| `attributes` | 키-값 메타데이터 | `{"http.method": "GET"}` |
| `events` | Span 내에서 발생한 이벤트 목록 | `"exception"`, `"cache.hit"` |

### TracerProvider → Tracer → Span

```
TracerProvider (전역 설정: Resource, Sampler, Processor)
    │
    ├── get_tracer("service-a") → Tracer 인스턴스
    │       └── start_as_current_span("op-1") → Span
    │
    └── get_tracer("service-b") → Tracer 인스턴스
            └── start_as_current_span("op-2") → Span
```

- **TracerProvider**: 하나의 애플리케이션에 하나만 존재합니다. Resource, Sampler, SpanProcessor를 관리합니다.
- **Tracer**: 모듈/컴포넌트별로 생성합니다. 이름으로 계측 출처를 식별합니다.
- **Span**: 실제 작업 단위. `start_as_current_span()` 컨텍스트 매니저로 생성하면 자동으로 시작/종료됩니다.

---

## 실습

### 1단계: 기본 TracerProvider 설정

`traces_basic.py` 파일을 생성합니다:

```python
# traces_basic.py
# TracerProvider를 설정하고 첫 Span을 생성

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.resources import Resource

# 1. Resource 생성: 이 서비스를 식별하는 메타데이터
resource = Resource.create({
    "service.name": "traces-basic-demo",
    "service.version": "1.0.0",
})

# 2. TracerProvider 생성
provider = TracerProvider(resource=resource)

# 3. ConsoleSpanExporter: Span 데이터를 콘솔에 출력
#    SimpleSpanProcessor: Span이 종료되면 즉시 Exporter로 전달
provider.add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)

# 4. 글로벌 TracerProvider로 등록
trace.set_tracer_provider(provider)

# 5. Tracer 취득 (모듈명을 식별자로 사용)
tracer = trace.get_tracer(__name__)

# 6. Span 생성
with tracer.start_as_current_span("my-first-span") as span:
    print(f"Trace ID: {span.get_span_context().trace_id:#034x}")
    print(f"Span ID:  {span.get_span_context().span_id:#018x}")
    print("첫 번째 Span이 실행 중입니다.")

# 7. Provider 종료 (미전송 데이터 flush)
provider.shutdown()
```

```bash
poetry run python traces_basic.py
```

출력에서 `trace_id`와 `span_id`가 0이 아닌 유효한 값인지 확인합니다.

### 2단계: 여러 Span 생성

`multiple_spans.py` 파일을 생성합니다:

```python
# multiple_spans.py
# 순차적인 작업을 여러 Span으로 분리

import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "multi-span-demo"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)


def fetch_user_data(user_id: str) -> dict:
    """사용자 데이터 조회를 시뮬레이션"""
    # 이 함수 호출이 하나의 Span으로 기록됨
    with tracer.start_as_current_span("fetch-user-data") as span:
        span.set_attribute("user.id", user_id)
        time.sleep(0.05)  # DB 쿼리 시뮬레이션
        return {"id": user_id, "name": "Alice", "email": "alice@example.com"}


def send_notification(user: dict, message: str):
    """알림 전송을 시뮬레이션"""
    with tracer.start_as_current_span("send-notification") as span:
        span.set_attribute("notification.type", "email")
        span.set_attribute("user.email", user["email"])
        time.sleep(0.03)  # 이메일 전송 시뮬레이션


def process_signup(user_id: str):
    """회원 가입 처리 — 전체 흐름을 하나의 Root Span으로 감싸기"""
    with tracer.start_as_current_span("process-signup") as span:
        span.set_attribute("signup.user_id", user_id)

        # 자식 Span 1: 사용자 데이터 조회
        user = fetch_user_data(user_id)

        # 자식 Span 2: 환영 알림 전송
        send_notification(user, "가입을 환영합니다!")

        span.add_event("signup.completed", {"user.name": user["name"]})


if __name__ == "__main__":
    process_signup("user-42")
    provider.shutdown()
```

```bash
poetry run python multiple_spans.py
```

출력에서 확인할 것:
- 세 개의 Span이 출력됩니다: `fetch-user-data`, `send-notification`, `process-signup`
- 세 Span의 `trace_id`가 모두 동일합니다 (같은 Trace에 속함)
- `fetch-user-data`와 `send-notification`의 `parent_id`가 `process-signup`의 `span_id`와 같습니다

### 3단계: Tracer 이름의 의미

여러 모듈에서 각각 Tracer를 생성하는 패턴을 확인합니다:

```python
# Tracer의 이름은 "계측 범위"(Instrumentation Scope)를 나타냄
# 동일한 TracerProvider에서 이름이 다른 Tracer를 여러 개 생성 가능

# 모듈별 Tracer 생성 패턴 (권장)
tracer_auth = trace.get_tracer("myapp.auth", "1.0.0")
tracer_payment = trace.get_tracer("myapp.payment", "1.0.0")
tracer_notification = trace.get_tracer("myapp.notification", "1.0.0")

# 각 Tracer로 생성된 Span에는 해당 Tracer의 이름이 기록됨
# → 백엔드에서 "이 Span이 어떤 모듈에서 생성되었는가?"를 확인 가능
```

---

## 주의사항

### Span 이름 작성 규칙

```python
# ✅ 좋은 예: 일반적이고 분류 가능한 이름
"GET /api/users"
"db.query"
"process-payment"
"send-email"

# ❌ 나쁜 예: 고유 ID나 변수를 포함한 이름
"GET /api/users/12345"       # → user_id는 속성으로
"query-SELECT * FROM users"  # → 쿼리문은 속성으로
```

Span 이름에 고유 값을 넣으면 카디널리티(cardinality)가 높아져 백엔드 성능에 악영향을 줍니다. 고유 값은 `span.set_attribute()`로 속성에 기록합니다.

### Provider 종료

```python
# 애플리케이션 종료 시 반드시 호출
# BatchSpanProcessor의 경우 버퍼에 남은 Span이 유실될 수 있음
provider.shutdown()
```

---

## 마무리

이번 단계에서 학습한 것:

- TracerProvider → Tracer → Span의 생성 흐름
- `start_as_current_span()` 컨텍스트 매니저를 통한 Span 자동 관리
- 부모-자식 Span 관계와 동일한 Trace ID 공유
- Span 이름 작성 시 카디널리티 고려

**다음 단계**: [04. Spans 심화](04-spans-in-depth.md)에서 Span에 속성, 이벤트, 상태 코드를 추가하고, Span의 다양한 종류(SpanKind)를 살펴봅니다.
