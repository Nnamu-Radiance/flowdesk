FROM nginx:alpine
COPY frontend/static/ /usr/share/nginx/html/
COPY frontend/static/ /usr/share/nginx/html/static/
RUN printf 'server {\n    listen 80;\n    root /usr/share/nginx/html;\n    index login.html;\n    location / {\n        try_files $uri $uri/ /login.html;\n    }\n}\n' \
    > /etc/nginx/conf.d/default.conf
EXPOSE 80
