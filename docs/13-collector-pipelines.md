# ⚙️ 13. Collector 파이프라인 (Collector Pipelines)

## 학습 목표

Collector의 Receiver, Processor, Exporter를 조합하여 데이터 필터링, 속성 변환, 라우팅 등 실전 파이프라인을 구성합니다.

---

## 핵심 개념

### 파이프라인 구조

Collector의 데이터 처리는 **Receiver → Processor → Exporter** 순서로 이루어집니다.

```
                    ┌── Pipeline 1 (traces) ──────────────┐
                    │                                      │
Receiver(OTLP) ──→ │ Processor(batch) → Processor(filter) │ ──→ Exporter(Jaeger)
                    │                                      │
                    └──────────────────────────────────────┘

                    ┌── Pipeline 2 (metrics) ─────────────┐
                    │                                      │
Receiver(OTLP) ──→ │ Processor(batch) → Processor(memory) │ ──→ Exporter(Prometheus)
                    │                                      │
                    └──────────────────────────────────────┘
```

- 하나의 Receiver가 여러 파이프라인에 공유될 수 있음
- 각 파이프라인은 독립적인 Processor 체인을 가짐
- 하나의 파이프라인에 여러 Exporter를 연결할 수 있음 (팬아웃)

---

## 실습

### 주요 Processor 종류

#### 1. Batch Processor

데이터를 모아서 일괄 전송합니다. 거의 모든 운영 환경에서 필수입니다.

```yaml
processors:
  batch:
    timeout: 5s              # 최대 대기 시간
    send_batch_size: 1024     # 한 배치의 최대 아이템 수
    send_batch_max_size: 2048 # 배치 절대 최대 크기
```

#### 2. Memory Limiter Processor

Collector의 메모리 사용량을 제한하여 OOM(Out of Memory)을 방지합니다.

```yaml
processors:
  memory_limiter:
    check_interval: 1s        # 메모리 체크 주기
    limit_mib: 512            # 하드 리밋 (512MB)
    spike_limit_mib: 128      # 스파이크 허용 범위
    # limit에 도달하면 데이터를 거부(drop)하여 프로세스를 보호
```

> **중요**: `memory_limiter`는 Processor 체인의 **첫 번째**에 위치해야 합니다.

#### 3. Attributes Processor

Span이나 Metric의 속성을 추가, 수정, 삭제합니다.

```yaml
processors:
  attributes/add:
    actions:
      # 속성 추가
      - key: environment
        value: production
        action: insert    # 없으면 추가, 있으면 무시

      # 속성 값 강제 덮어쓰기
      - key: deployment.region
        value: ap-northeast-2
        action: upsert    # 없으면 추가, 있으면 덮어쓰기

      # 속성 삭제
      - key: internal.debug.info
        action: delete

      # 속성 이름 변경
      - key: http.method
        new_key: http.request.method
        action: update

      # 속성 값을 해싱 (PII 보호)
      - key: user.email
        action: hash
```

#### 4. Resource Processor

모든 텔레메트리 데이터의 Resource 속성을 수정합니다.

```yaml
processors:
  resource:
    attributes:
      - key: cloud.provider
        value: aws
        action: upsert
      - key: cloud.region
        value: ap-northeast-2
        action: upsert
```

#### 5. Filter Processor

조건에 따라 데이터를 제거합니다.

```yaml
processors:
  filter/traces:
    error_mode: ignore
    traces:
      span:
        # 특정 경로의 Span 제외 (헬스 체크 등)
        - 'attributes["url.path"] == "/health"'
        - 'attributes["url.path"] == "/ready"'

  filter/metrics:
    error_mode: ignore
    metrics:
      metric:
        # 특정 메트릭 이름 제외
        - 'name == "http.server.active_requests" and resource.attributes["service.name"] == "debug-svc"'
```

#### 6. Transform Processor

OTTL(OpenTelemetry Transformation Language)을 사용하여 데이터를 변환합니다.

```yaml
processors:
  transform:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          # Span 이름에서 쿼리 파라미터 제거
          - replace_pattern(name, "\\?.*", "")

          # 특정 조건에서 속성 설정
          - set(attributes["priority"], "high")
            where attributes["http.response.status_code"] >= 500

    metric_statements:
      - context: datapoint
        statements:
          # 메트릭 값 단위 변환 (ms → s)
          - set(value_double, value_double / 1000.0)
            where metric.name == "request.duration.ms"
```

### 실전 파이프라인 예시

아래는 운영 환경에서 사용할 수 있는 통합 설정입니다:

`otel-collector-advanced.yml`:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  # 1. 메모리 보호 (반드시 첫 번째)
  memory_limiter:
    check_interval: 1s
    limit_mib: 512
    spike_limit_mib: 128

  # 2. 불필요한 데이터 필터링
  filter/health:
    error_mode: ignore
    traces:
      span:
        - 'attributes["url.path"] == "/health"'
        - 'attributes["url.path"] == "/metrics"'

  # 3. 환경 정보 추가
  resource:
    attributes:
      - key: deployment.environment
        value: production
        action: upsert

  # 4. 민감 정보 제거
  attributes/sanitize:
    actions:
      - key: user.email
        action: hash
      - key: db.query.text
        action: delete

  # 5. 배치 처리
  batch:
    timeout: 5s
    send_batch_size: 1024

exporters:
  debug:
    verbosity: basic

  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors:
        - memory_limiter    # 순서 중요!
        - filter/health
        - resource
        - attributes/sanitize
        - batch
      exporters: [otlp/jaeger, debug]

    metrics:
      receivers: [otlp]
      processors:
        - memory_limiter
        - resource
        - batch
      exporters: [prometheus, debug]

    logs:
      receivers: [otlp]
      processors:
        - memory_limiter
        - resource
        - attributes/sanitize
        - batch
      exporters: [debug]

  telemetry:
    logs:
      level: info
    metrics:
      address: 0.0.0.0:8888
```

### Processor 순서 권장 사항

```yaml
processors:
  # 1. memory_limiter — 항상 첫 번째 (메모리 보호)
  # 2. filter — 불필요한 데이터 조기 제거 (후속 처리 부하 감소)
  # 3. resource — Resource 속성 설정
  # 4. attributes — Span/Metric 속성 가공
  # 5. transform — 데이터 변환
  # 6. batch — 항상 마지막 (일괄 처리 최적화)
```

---

## Connector: 파이프라인 간 데이터 연결

Connector는 한 파이프라인의 출력을 다른 파이프라인의 입력으로 연결합니다. 예를 들어, Span 데이터에서 메트릭을 자동 생성할 수 있습니다.

```yaml
connectors:
  spanmetrics:
    histogram:
      explicit:
        buckets: [10ms, 50ms, 100ms, 250ms, 500ms, 1s]
    dimensions:
      - name: http.request.method
      - name: http.route

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/jaeger, spanmetrics]  # ← Connector가 Exporter로 작동

    metrics/spanmetrics:
      receivers: [spanmetrics]               # ← 같은 Connector가 Receiver로 작동
      processors: [batch]
      exporters: [prometheus]
```

---

## 마무리

이번 단계에서 학습한 것:

- 주요 Processor: `batch`, `memory_limiter`, `attributes`, `resource`, `filter`, `transform`
- Processor 순서의 중요성 (memory_limiter → filter → ... → batch)
- 민감 정보 처리 (해싱, 삭제)
- Connector를 통한 파이프라인 간 데이터 연결

**다음 단계**: [14. Sampling 전략](14-sampling-strategies.md)에서 데이터 수집량을 제어하는 다양한 샘플링 전략을 학습합니다.
