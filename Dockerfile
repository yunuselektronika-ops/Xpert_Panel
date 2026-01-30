ARG PYTHON_VERSION=3.12

# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/dashboard
COPY app/dashboard/package*.json ./
RUN npm ci --legacy-peer-deps
COPY app/dashboard/ ./
RUN npm run build

# Stage 2: Build Python dependencies
FROM python:$PYTHON_VERSION-slim AS python-build

ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl unzip gcc python3-dev libpq-dev iputils-ping \
    && curl -L https://github.com/Gozargah/Marzban-scripts/raw/master/install_latest_xray.sh | bash \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /code/
RUN python3 -m pip install --upgrade pip setuptools \
    && pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Stage 3: Final image
FROM python:$PYTHON_VERSION-slim

ENV PYTHON_LIB_PATH=/usr/local/lib/python${PYTHON_VERSION%.*}/site-packages
ENV PYTHONUNBUFFERED=1
WORKDIR /code

RUN apt-get update \
    && apt-get install -y --no-install-recommends iputils-ping curl \
    && rm -rf /var/lib/apt/lists/*

RUN rm -rf $PYTHON_LIB_PATH/*

COPY --from=python-build $PYTHON_LIB_PATH $PYTHON_LIB_PATH
COPY --from=python-build /usr/local/bin /usr/local/bin
COPY --from=python-build /usr/local/share/xray /usr/local/share/xray
COPY --from=python-build /usr/local/bin/xray /usr/local/bin/xray

COPY . /code
COPY --from=frontend-build /app/dashboard/dist /code/app/dashboard/build

RUN ln -s /code/marzban-cli.py /usr/bin/marzban-cli \
    && chmod +x /usr/bin/marzban-cli \
    && marzban-cli completion install --shell bash

EXPOSE 8000

CMD ["bash", "-c", "alembic upgrade head; python main.py"]
