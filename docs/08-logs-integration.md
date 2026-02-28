# 📝 08. Logs 연동 (Logs Integration)

## 학습 목표

Python 표준 `logging` 모듈과 OpenTelemetry Logs Bridge를 연동하여, 기존 로그를 OTel 파이프라인으로 통합하고 Trace와 연결하는 방법을 학습합니다.

---

## 핵심 개념

### OTel에서 Logs의 위치

OpenTelemetry의 Logs 접근 방식은 Traces, Metrics와 다릅니다:

| 신호 | OTel 접근 방식 |
|------|---------------|
| Traces | OTel API/SDK로 직접 생성 |
| Metrics | OTel API/SDK로 직접 생성 |
| Logs | **기존 로깅 프레임워크**(logging, loguru 등)를 **Bridge로 연결** |

OTel은 새로운 로깅 API를 제공하는 대신, 이미 사용 중인 로깅 프레임워크의 출력을 수집하여 OTLP 형식으로 내보내는 **Bridge(다리)** 역할을 합니다. 이를 통해:

- 기존 `logging.info()`, `logging.error()` 코드를 변경할 필요 없음
- 로그 데이터에 Trace ID, Span ID가 자동 추가됨
- 다른 신호(Traces, Metrics)와 동일한 파이프라인으로 내보내기 가능

### 내부 동작 흐름

```
logging.info("주문 처리 완료")
     │
     ▼
Python logging Handler (LoggingHandler)
     │
     ▼
OTel LoggerProvider → LogRecordProcessor → LogExporter
     │                                        │
     │  ← Trace Context 자동 첨부              │
     │     (현재 활성 Span의 trace_id, span_id) │
     ▼                                        ▼
LogRecord {                              OTLP/Console
  body: "주문 처리 완료",
  severity: INFO,
  trace_id: "abc123...",
  span_id: "def456...",
  resource: { service.name: "..." },
  attributes: { ... }
}
```

> **참고**: OpenTelemetry Python의 Logs API/SDK는 현재 **실험적(Experimental)** 상태입니다. API가 향후 변경될 수 있습니다. 패키지명에 `_logs`(언더스코어)가 사용되는 것은 이 때문입니다.

---

## 실습

### 1단계: 기본 Logs Bridge 설정

```bash
# Logs 관련 패키지는 opentelemetry-sdk에 포함되어 있어 추가 설치 불필요
# OTLP Log Exporter가 필요한 경우:
poetry add opentelemetry-exporter-otlp-proto-grpc
```

`logs_basic.py` 파일을 생성합니다:

```python
# logs_basic.py
# Python logging과 OTel Logs Bridge 연동

import logging

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    ConsoleLogExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.resources import Resource

# 1. Resource 설정
resource = Resource.create({
    "service.name": "logs-demo",
    "service.version": "1.0.0",
})

# 2. LoggerProvider 생성
logger_provider = LoggerProvider(resource=resource)

# 3. LogExporter + Processor 연결
#    SimpleLogRecordProcessor: 즉시 내보내기 (개발용)
logger_provider.add_log_record_processor(
    SimpleLogRecordProcessor(ConsoleLogExporter())
)

# 4. 글로벌 등록
set_logger_provider(logger_provider)

# 5. Python logging에 OTel Handler 추가
from opentelemetry.sdk._logs import LoggingHandler

handler = LoggingHandler(
    level=logging.DEBUG,
    logger_provider=logger_provider,
)

# 루트 로거에 핸들러 추가
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG)

# 6. 일반적인 Python logging 사용
logger = logging.getLogger("myapp.orders")

logger.info("애플리케이션 시작")
logger.debug("디버그 메시지: 설정 로드 완료")
logger.warning("경고: 캐시 미스 발생")
logger.error("에러: 데이터베이스 연결 실패", extra={
    "db.host": "localhost",
    "db.port": 5432,
})

# 7. Provider 종료
logger_provider.shutdown()
```

```bash
poetry run python logs_basic.py
```

출력에서 각 로그 레코드에 다음이 포함되는지 확인합니다:
- `severity_text`: INFO, DEBUG, WARNING, ERROR
- `body`: 로그 메시지
- `resource`: `service.name` 등

### 2단계: Logs + Traces 연결

로그를 Trace 안에서 기록하면 **자동으로 Trace ID와 Span ID가 로그에 첨부**됩니다.

```python
# logs_with_traces.py
# 로그와 트레이스를 연결하여 요청별 로그 추적

import logging
import time

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import (
    SimpleLogRecordProcessor,
    ConsoleLogExporter,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "logs-traces-demo"})

# --- Tracing 설정 ---
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# --- Logging 설정 ---
logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(
    SimpleLogRecordProcessor(ConsoleLogExporter())
)
set_logger_provider(logger_provider)

handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger("myapp.orders")


# --- 비즈니스 로직 ---
def process_order(order_id: str):
    # Span 내부에서 logging을 호출하면 trace_id, span_id가 자동 추가
    with tracer.start_as_current_span("process-order") as span:
        span.set_attribute("order.id", order_id)

        logger.info(f"주문 처리 시작: {order_id}")

        with tracer.start_as_current_span("validate-order"):
            logger.info(f"주문 검증 중: {order_id}")
            time.sleep(0.01)
            logger.info(f"주문 검증 완료: {order_id}")

        with tracer.start_as_current_span("charge-payment"):
            logger.info(f"결제 처리 중: {order_id}")
            try:
                # 결제 실패 시뮬레이션
                if order_id == "ORD-002":
                    raise ValueError("잔액 부족")
                time.sleep(0.02)
                logger.info(f"결제 완료: {order_id}")
            except ValueError as e:
                logger.error(f"결제 실패: {order_id} - {e}")
                span.set_status(trace.StatusCode.ERROR, str(e))
                span.record_exception(e)

        logger.info(f"주문 처리 완료: {order_id}")


# 실행
process_order("ORD-001")
print("\n" + "=" * 60 + "\n")
process_order("ORD-002")

# 종료
tracer_provider.shutdown()
logger_provider.shutdown()
```

```bash
poetry run python logs_with_traces.py
```

출력에서 확인할 것:
- **로그 레코드의 `trace_id`와 `span_id`**: 해당 로그가 어떤 Trace/Span 안에서 생성되었는지 표시
- ORD-001과 ORD-002의 로그가 **각각 다른 `trace_id`**를 가짐
- 같은 주문의 모든 로그는 **동일한 `trace_id`**를 공유

### 3단계: 구조화된 로그 (Structured Logging)

`extra` 파라미터를 사용하여 로그에 구조화된 속성을 추가합니다:

```python
# logs_structured.py
# 구조화된 속성이 포함된 로그

import logging
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import (
    SimpleLogRecordProcessor,
    ConsoleLogExporter,
)
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "structured-logs-demo"})

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(
    SimpleLogRecordProcessor(ConsoleLogExporter())
)
set_logger_provider(logger_provider)

handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger("myapp")

# 구조화된 속성 추가 (extra 딕셔너리)
logger.info("사용자 로그인 성공", extra={
    "user.id": "user-42",
    "user.role": "admin",
    "auth.method": "oauth2",
    "client.ip": "192.168.1.100",
})

logger.warning("API 요청 제한 초과", extra={
    "user.id": "user-42",
    "rate_limit.max": 100,
    "rate_limit.current": 105,
    "rate_limit.window_seconds": 60,
})

logger.error("파일 업로드 실패", extra={
    "file.name": "report.pdf",
    "file.size_bytes": 5242880,
    "error.code": "STORAGE_FULL",
})

logger_provider.shutdown()
```

---

## 기존 프로젝트에 Logs Bridge 도입하기

이미 logging을 사용하고 있는 프로젝트에서는 **로깅 설정 부분에만 OTel Handler를 추가**하면 됩니다:

```python
# 기존 코드
import logging
logging.basicConfig(level=logging.INFO)

# ↓ OTel Logs Bridge 추가 (기존 basicConfig 유지 가능)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter())  # Collector로 전송
)

# 기존 핸들러(콘솔, 파일 등)와 OTel 핸들러 공존
logging.getLogger().addHandler(
    LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
)

# 이후 모든 logging.info(), logging.error() 호출이
# 기존 출력 + OTel 파이프라인 양쪽으로 전달됨
```

---

## 마무리

이번 단계에서 학습한 것:

- **Logs Bridge**: 기존 Python logging을 OTel 파이프라인에 연결
- **Trace-Log 상관관계**: Span 내에서 생성된 로그에 trace_id, span_id 자동 첨부
- **구조화된 로그**: `extra` 파라미터를 통한 속성 추가
- **기존 프로젝트 도입**: Handler 추가만으로 기존 코드 수정 최소화

**다음 단계**: [09. 자동 계측](09-auto-instrumentation.md)에서 코드 수정 없이 Flask, requests 등의 라이브러리를 자동으로 계측하는 방법을 학습합니다.
