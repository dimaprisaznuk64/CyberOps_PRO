FROM python:3.13-slim

WORKDIR /gw

COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Файли потрапляють у /gw/gateway/ (призначення відносне до WORKDIR /gw), а
# код імпортує їх як `from gateway.config import ...` — тому gateway має бути
# пакетом на PYTHONPATH=/gw. Раніше тут було `COPY gateway/ gateway/`, але
# chmod і ENTRYPOINT вказували на /gw/entrypoint.sh, якого не існувало: файл
# лежав у /gw/gateway/. Збірка падала, а в стенді крутився старий образ до v1.2 —
# без rate limiting, security headers і TLS, хоча в коді вони були.
COPY gateway/ gateway/
RUN chmod +x /gw/gateway/entrypoint.sh

ENV PYTHONPATH=/gw

EXPOSE 8000

ENTRYPOINT ["/gw/gateway/entrypoint.sh"]