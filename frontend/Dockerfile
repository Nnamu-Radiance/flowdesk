FROM nginx:alpine
COPY frontend/static/ /usr/share/nginx/html/
RUN printf 'server {\n    listen 80;\n    root /usr/share/nginx/html;\n    index login.html;\n    location /static/ {\n        alias /usr/share/nginx/html/;\n    }\n    location / {\n        try_files $uri $uri/ /login.html;\n    }\n}\n' \
    > /etc/nginx/conf.d/default.conf
EXPOSE 80
