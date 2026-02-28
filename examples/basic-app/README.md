# 기초 데모 앱 (basic-app)

Flask 기반의 간단한 REST API 서버에 OpenTelemetry 계측을 적용한 데모 프로젝트입니다.

## 포함된 내용

- TracerProvider / MeterProvider 초기화
- Flask 자동 계측 (HTTP 요청 Span 자동 생성)
- 수동 Span 계측 (비즈니스 로직)
- Counter / Histogram 메트릭
- ConsoleExporter를 통한 콘솔 출력

## 실행 방법

```bash
cd examples/basic-app
poetry install
poetry run python app.py
```

다른 터미널에서:

```bash
# 아이템 목록 조회
curl http://localhost:5050/items

# 아이템 생성
curl -X POST http://localhost:5050/items \
  -H "Content-Type: application/json" \
  -d '{"name": "노트북", "price": 1200000}'

# 개별 아이템 조회
curl http://localhost:5050/items/1
```

콘솔에 Span과 Metric 데이터가 출력됩니다.

## Jaeger로 전송하기 (선택)

Jaeger를 실행한 상태에서 환경 변수를 설정하면 OTLP로 전송됩니다:

```bash
docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one:latest

export OTEL_EXPORTER_ENDPOINT=http://localhost:4317
poetry run python app.py
```

Jaeger UI: http://localhost:16686
