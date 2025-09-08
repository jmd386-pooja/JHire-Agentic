# Node + Python in one image
FROM node:20-bullseye AS base
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- install Next deps ---
COPY apps/web/package*.json ./apps/web/
RUN cd apps/web && npm ci

# --- copy sources ---
COPY . .

# --- python deps ---
RUN pip3 install --no-cache-dir -r apps/ai/requirements.txt

# --- build Next ---
RUN cd apps/web && npm run build

# run both: Python (8000) + Next (3000)
EXPOSE 3000 8000
CMD bash -lc "python3 apps/ai/bridge_http.py & cd apps/web && npm start"
