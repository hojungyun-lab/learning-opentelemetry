FROM python:3.12-slim

WORKDIR /app

# 공유 모듈 복사
COPY shared/ /app/shared/

# 서비스 의존성 설치
COPY inventory-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 서비스 코드 복사
COPY inventory-service/ /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
