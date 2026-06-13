# Contexto do Projeto

Resumo curto para acelerar desenvolvimento sem reler o código inteiro.

## Fluxo principal

1. `orchestrator.py` recebe o intervalo de datas.
2. `core.new_moons()` encontra luas novas no intervalo.
3. `pipeline.run_batch()` filtra candidatos e calcula contatos.
4. `geometry.*` calcula caixa, mapa de obscuracao e linha central.
5. `core.magnitude.compute_surface_max_magnitude()` estima a magnitude no ponto de maior obscuracao.
6. `plotting.plot_obscuration_map()` gera a imagem final.

## Arquivos

### `orchestrator.py`
Ponto de entrada da aplicacao. Faz parse das datas, carrega efemeride, roda a simulacao, calcula geometria fisica e salva os mapas. Usa `Timer` para medir etapas.

### `core/__init__.py`
Reexporta a API central do pacote `core`:
`new_moons`, `is_possible_eclipse`, `refine_maximum`, `compute_contacts`, `classify_eclipse`, `eclipse_title`.

### `core/constants.py`
Constantes astronomicas em km: raio do Sol, Lua, Terra e unidade astronomica.

### `core/phases.py`
Encontra luas novas com `skyfield.almanac.moon_phases` e filtra a fase 0.

### `core/eclipse_filter.py`
Filtro grosseiro de candidato. Verifica se, perto da lua nova, a separacao Sol-Lua pode permitir eclipse.

### `core/maximum.py`
Refina o instante de maior aproximacao Sol-Lua com busca em duas passadas.

### `core/contacts.py`
Calcula C1, C2, C3 e C4 por mudanca de sinal entre separacao aparente e limite geometrico.

### `core/classification.py`
Classifica eclipse em `Parcial`, `Total`, `Anular` ou `Total/Anular` com base na obscuracao maxima e nos raios aparentes.

### `core/magnitude.py`
Calcula a magnitude de superficie no ponto lat/lon de maior obscuracao.

### `geometry/__init__.py`
Reexporta `eclipse_bounding_box`, `central_path` e `eclipse_obscuration_map`.

### `geometry/geodesy.py`
Conversoes geodesicas auxiliares. `geodetic_to_ecef()` converte lat/lon para ECEF; `ecef_to_gcrs()` aplica rotacao simples em torno do eixo Z.

### `geometry/central_path.py`
Calcula a linha central do eclipse ao longo do intervalo entre C2 e C3, projetando o eixo Sol-Lua ate a superficie da Terra.

### `geometry/bounding_box.py`
Calcula uma caixa lat/lon aproximada da faixa de obscuracao usando uma grade grosseira e expansão de margem.

### `geometry/surface_map.py`
Modulo mais pesado do projeto. Amostra o intervalo temporal, monta grade global, distribui trabalho em processos e calcula a obscuracao maxima por ponto da superficie.

### `geometry/obscuration.py`
Funcoes matematicas para angulo entre vetores e area de intersecao entre discos. `eclipse_obscuration_vec()` devolve a fração obscura do Sol.

### `infrastructure/__init__.py`
Vazio. Serve apenas como pacote.

### `infrastructure/config.py`
Define caminhos base do projeto, efemeride `de440.bsp` e diretório `outputs/`.

### `infrastructure/ephemeris.py`
Carrega e cacheia a efemeride e a escala de tempo. Se o arquivo nao existir, baixa automaticamente.

### `pipeline/__init__.py`
Vazio. Pacote do fluxo em lote.

### `pipeline/batch.py`
Processa cada lua nova em paralelo: filtra eclipse possivel, refina maximo, calcula contatos e retorna eventos ordenados por tempo de maximo.

### `plotting/__init__.py`
Reexporta `plot_obscuration_map`.

### `plotting/map_plot.py`
Gera o mapa final. Tenta Cartopy, cai para fallback com Natural Earth se necessario. Desenha obscuracao, linha central, marcador do maximo, legenda e quadro com dados.

### `plotting/formatting.py`
Formatacao de tempo, duracao e escolha de canto para a caixa de informacoes no mapa.

### `plotting/colormaps.py`
Define paletas discretas e limites de cor para a obscuracao.

### `utils/__init__.py`
Vazio. Pacote utilitario.

### `utils/timer.py`
Context manager simples para medir tempo de blocos e imprimir a duracao.

### `requirements.txt`
Dependencias principais: `matplotlib`, `numpy`, `pyshp`, `scipy`, `skyfield`.

### `README.md`
Visao geral de uso, dependencias, instalacao e saidas geradas.

## Dependencias importantes

- `skyfield`: efemerides, tempos e posicoes astronomicas.
- `numpy`: calculo numerico e grades.
- `scipy`: suavizacao e interpolacao no mapa.
- `matplotlib`: plot final.
- `cartopy` e `shapefile` sao opcionais no runtime do mapa.

## Pontos de atenção

- O projeto depende do arquivo `data/ephemeris/de440.bsp`.
- `surface_map.py` e `map_plot.py` sao os arquivos mais caros em tempo de execucao.
- `pipeline/batch.py` e `geometry/surface_map.py` usam multiprocessamento.
- A saida final vai para `outputs/`.
