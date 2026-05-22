FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-create prisma's nodeenv with Node 20 LTS to avoid the npm 11 bug in Node 26
# prisma-client-py stores its nodeenv at /root/.cache/prisma-python/nodeenv
# If this directory exists, prisma skips downloading Node 26
RUN nodeenv --prebuilt --node=20.19.0 /root/.cache/prisma-python/nodeenv

# Install the prisma CLI inside the pre-created nodeenv
RUN . /root/.cache/prisma-python/nodeenv/bin/activate && npm install prisma@5.17.0

COPY . .

RUN prisma generate

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
