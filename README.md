
Simulador numerico para identificar eclipses solares em um intervalo de datas,
calcular dados fisicos principais e gerar mapas de obscuracao.

- Python 3.13 ou superior
- Git
- Dependencias listadas em `requirements.txt`

O projeto baixa automaticamente a efemeride `de440.bsp` na primeira execucao e
salva o arquivo em `data/ephemeris/`. Os dados cartograficos Natural Earth
tambem sao baixados automaticamente quando o mapa precisa usar o fallback sem
Cartopy.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Executar com o intervalo padrao:

```powershell
.\.venv\Scripts\python.exe orchestrator.py
```

Executar com datas informadas:

```powershell
.\.venv\Scripts\python.exe orchestrator.py 2024-01-01 2024-12-31
```

As imagens geradas sao salvas em `outputs/`.

- `core/`: calculos astronomicos centrais, classificacao e contatos.
- `geometry/`: geometria da sombra, grade de superficie e caminho central.
- `infrastructure/`: configuracao de caminhos e carregamento de efemerides.
- `pipeline/`: processamento em lote dos eventos candidatos.
- `plotting/`: mapas, cores e formatacao visual.
- `utils/`: utilitarios gerais.

Os seguintes caminhos sao ignorados pelo Git:

- `.venv/`
- `outputs/`
- `data/ephemeris/`
- `data/natural_earth/`
- `__pycache__/`
