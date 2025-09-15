# Build step
FROM node:20 AS build
WORKDIR /app

# install deps
COPY frontend/package*.json ./
RUN npm ci

# build with API URL injected at build time (Vite-style)
ARG VITE_API_BASE=""
ENV VITE_API_BASE=$VITE_API_BASE

COPY frontend ./
RUN npm run build

# Serve step
FROM nginx:alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
