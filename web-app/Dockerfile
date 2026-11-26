# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: deps — install production + dev dependencies
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: builder — compile the Next.js application
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable Next.js telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8081
RUN --mount=type=cache,target=/app/.next/cache npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: runner — minimal production image
# ─────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs \
 && adduser  --system --uid 1001 nextjs

# Copy only the artifacts needed to run the server
COPY --from=builder /app/public          ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static

USER nextjs

EXPOSE 3000

# Next.js standalone server entry point
CMD ["node", "server.js"]
