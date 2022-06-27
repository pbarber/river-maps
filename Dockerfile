FROM python:3.8.8
ENV PYTHONUNBUFFERED 1

WORKDIR /usr/src/app

# Setup SSH with secure root login
RUN apt-get update \
 && apt-get install -y openssh-server netcat \
 && mkdir /var/run/sshd \
 && echo 'root:password' | chpasswd \
 && sed -i 's/\#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
EXPOSE 22

RUN apt-get install -y binutils libproj-dev gdal-bin libgdal-dev libspatialindex-dev

COPY requirements.txt /usr/src/app/
RUN pip install -r requirements.txt

COPY requirements-dev.txt /usr/src/app/
RUN pip install -r requirements-dev.txt

CMD ["/usr/sbin/sshd", "-D"]
