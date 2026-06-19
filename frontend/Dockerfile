FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Use npm instead of pnpm to avoid build-script approval issues
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
