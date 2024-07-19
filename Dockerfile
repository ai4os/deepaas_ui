FROM python:3.8

# Env vars:
# * DURATION
#   Time after which the container will be automatically killed
# * DEEPAAS_IP
#   When module launched in another container, the IP is retrived with the followng command
#   docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <container-id>
ENV DURATION=10m
ENV DEEPAAS_IP=0.0.0.0
ENV DEEPAAS_PORT=5000
ENV UI_PORT=80

RUN apt-get update && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

CMD ["bash", "./nomad.sh"]
