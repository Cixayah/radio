# Radio Ad Detector

Detector automatizado de anúncios em rádios online brasileiras.

O projeto captura áudio em ciclos, aplica VAD (detecção de fala), transcreve com Whisper via Groq, classifica trechos com regras + LLM e salva:

- áudios detectados como anúncio
- logs de execução
- relatório Excel consolidado

## Como Funciona

1. Gravadores paralelos capturam streams das rádios configuradas em janelas de 60s.
2. Cada áudio passa por VAD (Silero) para descartar trechos com pouca fala.
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

Durante a execução, você verá no terminal:

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
