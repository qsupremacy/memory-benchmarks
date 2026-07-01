FROM python:3.12-slim

# Use Chinese mirrors for apt and pip to speed up builds in CN
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# System deps for spaCy native extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Shallow git clone for mem0ai to reduce memory + faster install
RUN GIT_CLONE_PROTECTION_ACTIVE=0 pip install -r requirements.txt
    #--no-cache-dir \
    #--extra-index-url https://mirrors.aliyun.com/pypi/simple/ \
    #--trusted-host mirrors.aliyun.com \
    #-r requirements.txt

# Install spaCy English model from local source (pre-downloaded via gh-proxy)
COPY en_core_web_sm /usr/local/lib/python3.12/site-packages/en_core_web_sm

# Allow "sagemaker" as an embedding provider in mem0's config validator
RUN sed -i 's/"aws_bedrock",/"aws_bedrock", "sagemaker",/' \
    /usr/local/lib/python3.12/site-packages/mem0/embeddings/configs.py

# History directory
RUN mkdir -p /app/history

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
