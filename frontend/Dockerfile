FROM nginx:alpine
COPY frontend/static/ /usr/share/nginx/html/
RUN printf 'server {\n    listen 80;\n    root /usr/share/nginx/html;\n    index login.html;\n    rewrite ^/static/(.*) /$1 last;\n    location / {\n        try_files $uri $uri/ /login.html;\n    }\n}\n' \
    > /etc/nginx/conf.d/default.conf
EXPOSE 80
