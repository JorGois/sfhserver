FROM python:3.9-alpine

ENV PATH /usr/local/bin:$PATH
RUN apk --update add bash nano
COPY requirements.txt ./
RUN pip install -r requirements.txt

WORKDIR /usr/src/app
COPY config.yml .
COPY src/* .
ENTRYPOINT [ "python3", "./server.py" ]
# expose port
EXPOSE 8080