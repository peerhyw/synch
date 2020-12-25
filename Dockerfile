FROM python:3
RUN mkdir -p /synchp
WORKDIR /synchp
COPY pyproject.toml poetry.lock /synchp/
RUN pip3 install poetry
ENV POETRY_VIRTUALENVS_CREATE false
RUN poetry install --no-root
COPY . /synchp
RUN poetry install