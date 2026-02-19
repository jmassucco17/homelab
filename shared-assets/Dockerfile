# NOTE: nginx version must stay in sync with homepage/Dockerfile and blog/Dockerfile
FROM nginx:1.28-alpine
COPY ./assets /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
