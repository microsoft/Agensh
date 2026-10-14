# mini-router (R7 sidecar) — one process per agent.
# Multi-stage: TS build → minimal runtime.
FROM node:20-alpine AS build
WORKDIR /build
COPY package.json package-lock.json* tsconfig.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install --no-audit --no-fund; fi
COPY src ./src
COPY sql ./sql
RUN npx tsc

FROM node:20-alpine AS runtime
WORKDIR /app
COPY --from=build /build/dist ./dist
COPY --from=build /build/node_modules ./node_modules
COPY --from=build /build/sql ./sql
ENV NODE_ENV=production
EXPOSE 8645
CMD ["node", "dist/main.js"]
