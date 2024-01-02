FROM continuumio/miniconda3
RUN conda update --all -y
COPY . ./
RUN conda env create -f prod-environment.yml
RUN sed -i 's/importlib_metadata/importlib.metadata/g' /opt/conda/envs/market-returns/lib/python3.11/site-packages/dash/dash.py
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "market-returns", "gunicorn", "--bind", "0.0.0.0:8080", "returns_dashboard:server"]