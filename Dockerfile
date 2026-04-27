FROM python:3.11-slim

WORKDIR /app

# 使用清华镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host https://pypi.tuna.tsinghua.edu.cn

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY push.py .

# 数据目录
RUN mkdir -p /data

# 容器启动命令
CMD ["python", "push.py"]
