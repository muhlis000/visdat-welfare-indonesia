# visdat-welfare-indonesia
Project UAS Visdat 2025/2026

## Build static story assets

The deployed Streamlit app reads its tabular story data locally and fetches
the map geometry from cached static assets. After changing the source
`data/processed/df_geo.parquet`, install `requirements-build.txt` and run:

```powershell
python scripts/build_story_assets.py
```

Commit the generated files in `app/static/` with the application so they are
available to Streamlit's static file server. The runtime dependencies in
`requirements.txt` do not include GeoPandas or PyArrow.
