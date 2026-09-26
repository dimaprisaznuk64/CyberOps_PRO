FROM python:3.13-slim

WORKDIR /gw

COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway/ gateway/
RUN chmod +x /gw/entrypoint.sh

ENV PYTHONPATH=/gw

EXPOSE 8000

ENTRYPOINT ["/gw/entrypoint.sh"]