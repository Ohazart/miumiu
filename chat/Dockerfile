# syntax=docker/dockerfile:1
FROM node:24-slim AS build
WORKDIR /app
COPY chat/package.json chat/package-lock.json ./
RUN npm ci
COPY chat/server.js ./
COPY chat/public ./public
RUN node --check server.js

FROM node:24-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
RUN groupadd -g 1000 app && \
    useradd -u 1000 -g 1000 -m -s /usr/sbin/nologin app
COPY --from=build --chown=1000:1000 /app/node_modules ./node_modules
COPY --chown=1000:1000 chat/server.js chat/package.json ./
COPY --chown=1000:1000 chat/public ./public
EXPOSE 3000
USER 1000:1000
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
