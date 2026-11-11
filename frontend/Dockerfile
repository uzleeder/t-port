# T-Port web — production image (Next.js standalone output)
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

FROM node:22-alpine AS build
WORKDIR /app
# Rewrites (/api -> backend) are resolved at build time, so the API address is a build arg.
ARG API_INTERNAL_URL=http://api:8000
ENV NEXT_TELEMETRY_DISABLED=1 API_INTERNAL_URL=${API_INTERNAL_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=2028 HOSTNAME=0.0.0.0
RUN addgroup -S tport && adduser -S tport -G tport
COPY --from=build --chown=tport:tport /app/.next/standalone ./
COPY --from=build --chown=tport:tport /app/.next/static ./.next/static
COPY --from=build --chown=tport:tport /app/public ./public
USER tport
EXPOSE 2028
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1:2028/ >/dev/null || exit 1
CMD ["node", "server.js"]
