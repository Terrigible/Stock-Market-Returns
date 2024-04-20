FROM continuumio/miniconda3
RUN conda update --all -y
COPY . ./
RUN conda env create -f prod-environment.yml
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "market-returns", "gunicorn", "--bind", "0.0.0.0:8080", "returns_dashboard:server"]