# Radio Ad Detector

Detector automatizado de anúncios em rádios online brasileiras com interface gráfica simples para monitoramento.

O projeto captura áudio em ciclos, aplica VAD (detecção de fala), transcreve com Whisper via Groq, classifica trechos com regras + LLM e salva:

- áudios detectados como anúncio
- logs de execução
- relatório Excel consolidado

## Como Funciona

1. Gravadores paralelos capturam streams das rádios configuradas em janelas de 60s.
2. Cada áudio passa por VAD leve (FFmpeg `silencedetect`) para descartar trechos com pouca fala.
3. O áudio é transcrito (Groq Whisper).
4. Heurísticas identificam sinais de anúncio (CTA, preço, telefone, contexto comercial).
5. Um LLM (Groq) classifica e estrutura os anúncios detectados.
6. O sistema salva o MP3 detectado e atualiza o arquivo Excel.

## Estrutura do Projeto

```text
main.py
requirements.txt
app/
  __init__.py
  config.py
  detector.py
  excel_report.py
  heuristics.py
  recorder.py
  utils.py
radio_capture/
  detected_ads/
  logs/
  temp_audios/
```

## Pré-requisitos

- Python 3.10+
- FFmpeg instalado e disponível no PATH
- Chave de API da Groq (`GROQ_API_KEY`)

### Verificar FFmpeg

```bash
ffmpeg -version
```

Se o comando não for encontrado, instale o FFmpeg e adicione ao PATH do sistema.

Alternativas suportadas pelo app (sem depender de PATH):

- Definir variável de ambiente `FFMPEG_PATH` apontando para o executável.
- Colocar `ffmpeg.exe` em `bin/ffmpeg.exe` na raiz do projeto (modo desenvolvimento).
- No executável empacotado, manter `ffmpeg.exe` na mesma pasta do `.exe`.

## Instalação

### 1. Clonar e acessar o projeto

```bash
git clone <url-do-repositorio>
cd radio
```

### 2. Criar e ativar ambiente virtual

Windows (Git Bash):

```bash
python -m venv venv
source venv/Scripts/activate
```

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz com:

```env
GROQ_API_KEY=sua_chave_aqui
```

## Execução

```bash
python main.py
```

Esse comando abre a interface gráfica. Se preferir o modo de terminal, use:

```bash
python main.py --cli
```

Na interface gráfica, você pode:

- iniciar e parar a captura com um clique
- pausar e retomar rádios individualmente durante a execução
- escolher quais rádios entram no monitoramento antes de iniciar
- acompanhar os logs em tempo real
- abrir a pasta `radio_capture/`

No modo de terminal, você verá no terminal:

- status dos gravadores
- pontuação heurística dos trechos
- anúncios detectados e confiança
- confirmação de gravação no Excel

Para parar, use `Ctrl+C`.

## Saídas Geradas

As saídas ficam em `radio_capture/`:

- `temp_audios/`: áudios temporários de captura
- `detected_ads/`: anúncios salvos como MP3
- `logs/`: espaço reservado para logs
- `relatorio_anuncios.xlsx`: relatório principal

## Executável no Windows

O projeto inclui scripts de build para gerar um executável com PyInstaller.

### Build padrão

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Execute o build (se ffmpeg não estiver disponível, use o build leve):

```bat
build_exe.bat
```

O executável será gerado em `dist/RadioAdDetector.exe`.

### Build Leve (reduzir tamanho e empacotar ffmpeg)

Este é o build recomendado para distribuição a outras máquinas, pois:
- Cria um ambiente isolado de build
- Empacotar ffmpeg junto (sem dependência de instalação global)
- Reduz o tamanho final com otimizações agressivas

```bat
build_exe_light.bat
```

Saídas:
- `dist/RadioAdDetector.exe` — Executável principal
- `dist/_internal/` — Dependências do app (inclui ffmpeg em `_internal/bin/ffmpeg.exe`)

### Resolução de FFmpeg

O app procura ffmpeg nesta ordem:
1. Variável de ambiente `FFMPEG_PATH` (se definida)
2. FFmpeg no `PATH` do sistema
3. Pasta `bin/ffmpeg.exe` da distribuição (empacotado no build leve)
4. `_internal/bin/ffmpeg.exe` quando rodando como executável congelado

Se rodar em outra máquina e não tiver ffmpeg:
- **Opção 1 (recomendado):** Distribua a pasta `dist` completa (`RadioAdDetector.exe` + `_internal`) — ffmpeg já está incluído
- **Opção 2:** Instale ffmpeg no sistema (`choco install ffmpeg` ou baixar de ffmpeg.org)
- **Opção 3:** Defina `FFMPEG_PATH=C:\caminho\para\ffmpeg.exe` e execute o `.exe`

Se existir um arquivo `.env` na raiz no momento do build, ele será empacotado junto ao app para facilitar o envio ao usuário final.

> **Nota:** O modo `--onedir` abre mais rápido e evita o custo de extração do `--onefile`,
> deixando a experiência mais leve na execução.

### Abas do Excel

- `Anúncios Detectados`
- `Resumo por Rádio`
- `Resumo por Anunciante`

## Configuração

As configurações principais estão em `app/config.py`:

- `STATIONS`: rádios monitoradas
- `RECORD_DURATION`: duração de cada ciclo de captura
- `GROQ_WHISPER_MODEL`: modelo de transcrição
- `GROQ_LLM_MODEL`: modelo de classificação
- thresholds de detecção (`MIN_SPEECH_RATIO`, `MIN_SPEECH_SEGS`, `AD_COOLDOWN_SECONDS`)

## Personalizar Rádios

Edite `STATIONS` em `app/config.py`:

```python
STATIONS = {
    "Minha_Radio": "https://meu-stream/ao-vivo",
}
```

Depois de iniciar pela interface, você pode pausar/retomar cada rádio pelo painel de gerenciamento sem precisar encerrar o monitoramento.

## Solução de Problemas

- Erro `GROQ_API_KEY não encontrada`:
  - Verifique se o `.env` existe na raiz e contém `GROQ_API_KEY` válido.
- Erro de gravação com FFmpeg:
  - Confirme se `ffmpeg -version` funciona no mesmo terminal da execução.
- Poucos anúncios detectados:
  - Ajuste thresholds em `app/config.py` e revise heurísticas em `app/heuristics.py`.

## Observações

- O projeto usa chamadas de IA (Groq), portanto depende de internet.
- A qualidade da detecção pode variar por rádio, sotaque, ruído e qualidade do stream.
- Para reduzir falsos positivos/negativos, ajuste prompts e heurísticas conforme seu cenário.
