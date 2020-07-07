FROM python

MAINTAINER harry.kodden@surf.nl

RUN apt-get update
RUN apt-get install -y build-essential
RUN apt-get install -y --no-install-recommends \
    python-pip \
    python-wheel \
    python-setuptools

RUN apt-get install -y libsasl2-dev python-dev libldap2-dev libssl-dev

ADD requirements.txt .

RUN pip install -r requirements.txt

WORKDIR /app
