# Compile the TypeScript sidecar, then copy only runtime code and dependencies.
FROM node:20-alpine AS build
WORKDIR /build
COPY package.json package-lock.json tsconfig.json ./
RUN npm ci --no-audit --no-fund
COPY src ./src
RUN npx tsc && npm prune --omit=dev --ignore-scripts --no-audit --no-fund

FROM node:20-alpine AS runtime
WORKDIR /app
COPY --from=build /build/dist ./dist
COPY --from=build /build/node_modules ./node_modules
ENV NODE_ENV=production
EXPOSE 8645
CMD ["node", "dist/main.js"]
