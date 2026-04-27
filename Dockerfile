FROM python:3.11-slim

WORKDIR /app

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host https://pypi.tuna.tsinghua.edu.cn

RUN pip install --no-cache-dir PyYAML

COPY push.py .
COPY settings.yaml .
COPY docker-entrypoint.sh .

RUN mkdir -p /data

ENTRYPOINT ["/app/docker-entrypoint.sh"]
