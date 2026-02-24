FROM node:20-alpine AS ts-builder
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY games/app/static ./static
RUN npx tsc -p static/tsconfig.json

FROM ghcr.io/jmassucco17/homelab/python-base:latest
COPY games/app ./app
COPY --from=ts-builder /build/static ./app/static
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
