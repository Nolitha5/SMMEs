FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/. .
ARG VITE_API_URL=/api/v1
ARG VITE_AUTH_MODE=firebase
ENV VITE_API_URL=$VITE_API_URL VITE_AUTH_MODE=$VITE_AUTH_MODE
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
