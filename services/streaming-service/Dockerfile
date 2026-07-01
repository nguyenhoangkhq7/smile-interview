# Stage 1: Builder
FROM node:24-alpine AS builder

WORKDIR /app

ENV NODE_ENV=development

# Copy dependency configuration
COPY package*.json ./

# Install all dependencies (including devDependencies if any)
RUN npm ci

# Prune non-production dependencies to prepare node_modules for production
RUN npm prune --omit=dev

# Stage 2: Runner
FROM node:24-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Use the built-in non-root node user for security
USER node

# Copy production node_modules from builder
COPY --chown=node:node --from=builder /app/node_modules ./node_modules
COPY --chown=node:node package.json ./
COPY --chown=node:node src/ ./src/

EXPOSE 8001

CMD ["npm", "start"]
