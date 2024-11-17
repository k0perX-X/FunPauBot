FROM python:alpine as base
FROM base as builder
COPY requirements.txt /requirements.txt
RUN pip install --user -r /requirements.txt

FROM base
COPY --from=builder /root/.local /root/.local
COPY src /app
WORKDIR /app

ENV PATH=/root/.local/bin:$PATH
ENV TZ=Europe/Moscow

CMD ["python", "main.py"]