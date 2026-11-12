# EvolvXSI workspace (Next.js). The API address is fixed at build time because
# Next.js bakes its rewrites into the build:
#   docker build --build-arg INTERNAL_URL=http://api:8080 -t evolvxsi-web .
FROM node:22-slim AS build
RUN npm install -g bun@1.4.4
WORKDIR /app
COPY package.json bun.lock ./
# The workspace packages build themselves while installing, so their sources come first.
COPY lib ./lib
RUN bun install --frozen-lockfile
COPY . .
RUN cd lib/shared && bun run build && cd ../opal && bun run build
ARG INTERNAL_URL=http://api:8080
ENV INTERNAL_URL=$INTERNAL_URL NEXT_TELEMETRY_DISABLED=1
RUN npx next build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
