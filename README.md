# MRFUTBOL

## Ejecutar en Windows

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Para cargar la bitácora histórica, coloca `Bitacora_Completa_Over05_2026-10-31.csv` junto a `app.py` antes de iniciar la aplicación, o impórtala desde **Bóveda Privada (Admin) → Fusionar CSV de Bitácora**. La aplicación guarda la bitácora fusionada en `.boveda_ml_over05_mrfutbol.json`.

La clave opcional de API-Football se configura como `API_FOOTBALL_KEY` en las variables de entorno o en `.streamlit/secrets.toml`. No guardes claves privadas dentro de `app.py`.
