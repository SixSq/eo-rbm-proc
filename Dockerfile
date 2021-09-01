FROM docker.pkg.github.com/snap-contrib/docker-snap/snap:latest

COPY requirements.txt /tmp/

RUN pip install -r /tmp/requirements.txt

COPY src/eo-rbm.py /app/eo-rbm.py

# Bring globcover and other auxiliary data
COPY test-data/S1A_IW_GRDH_1SDV_20180415T163146_20180415T163211_021480_025003_8E79.zip /tmp/S1A_IW_GRDH_1SDV_20180415T163146_20180415T163211_021480_025003_8E79.zip
COPY test-data/island_boundary2.shp /tmp/island_boundary2.shp
USER root
RUN /app/eo-rbm.py \
    --product-path /tmp/S1A_IW_GRDH_1SDV_20180415T163146_20180415T163211_021480_025003_8E79.zip \
    --shape-path /tmp/island_boundary2.shp \
    --result-path /tmp/final_mask && rm -rf /tmp/*

ENTRYPOINT ["/app/eo-rbm.py"]
