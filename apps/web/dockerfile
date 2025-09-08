# Base image
FROM node:20-alpine3.19 

# Install Python and other dependencies
RUN apk update && \
    apk add --no-cache \
    python3 \
    py3-pip \
    gcc \
    musl-dev \
    python3-dev

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./
COPY prisma ./prisma/

# Install Node.js dependencies and generate Prisma client
RUN npm i && \
    npx prisma generate 

# Copy the rest of the application
COPY . .

# Set up Python virtual environment and install requirements
COPY requirements.txt .
ENV VIRTUAL_ENV=/app/.venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN . $VIRTUAL_ENV/bin/activate && \
    pip install --no-cache-dir -r requirements.txt

# Verify PyPDF2 installation
RUN . $VIRTUAL_ENV/bin/activate && \
    python3 -c "import PyPDF2; print('PyPDF2 installed successfully')"

# Build Next.js
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
ENV PORT=3002
ENV HOSTNAME=localhost

# Build the Next.js application
RUN npm run build

# Create non-root user and set permissions
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs && \
    chown -R nextjs:nodejs /app

# Create a startup script with migrations and seeding
RUN echo '#!/bin/sh' > /app/start.sh && \
    echo 'npx prisma migrate deploy' >> /app/start.sh && \
    echo 'npx prisma db seed' >> /app/start.sh && \
    echo '. $VIRTUAL_ENV/bin/activate && npm run start' >> /app/start.sh && \
    chmod +x /app/start.sh

USER nextjs

EXPOSE 3002

# Use the startup script as the CMD
CMD ["/app/start.sh"] 