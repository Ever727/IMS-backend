FROM python:3.9

ENV DEPLOY 1

ENV DJANGO_ENV development

WORKDIR /app

RUN apt-get update && apt-get install -y redis-server

COPY requirements.txt .

RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

EXPOSE 80

CMD ["./start.sh"]