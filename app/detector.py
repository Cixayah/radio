import datetime
import json
import os
import queue
import re
import shutil
import threading
import traceback

import librosa
import torch

from .config import (
    AD_COOLDOWN_SECONDS,
    GROQ_LLM_MODEL,
    GROQ_WHISPER_MODEL,
    MIN_SPEECH_RATIO,
    MIN_SPEECH_SEGS,
    RECORD_DURATION,
    STATIONS,
    TRANSCRIPTION_CAP,
    groq_client,
)
from .excel_report import ExcelReportManager
from .heuristics import heuristic_score, is_retail_anchor, name_in_text, should_skip
from .recorder import recorder_worker
from .utils import br_display, br_now, br_timestamp, fix_transcription, safe_filename


class AdDetector:
    def __init__(self):
        self.base_path = "radio_capture"
        self.audio_path = os.path.join(self.base_path, "temp_audios")
        self.log_path = os.path.join(self.base_path, "logs")
        self.ads_path = os.path.join(self.base_path, "detected_ads")
        self.report_path = os.path.join(self.base_path, "relatorio_anuncios.xlsx")

        for folder in [self.audio_path, self.log_path, self.ads_path]:
            os.makedirs(folder, exist_ok=True)

        self._recent_ads: dict[str, datetime.datetime] = {}
        self.start_time: datetime.datetime | None = None
        self._session_excel_rows: dict[str, int] = {}
        self.excel = ExcelReportManager(self.report_path)

        print("🔧 Carregando Silero VAD...")
        self.vad_model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True,
        )
        self.get_speech_timestamps = utils[0]
        print(f"☁️  Groq | Whisper: {GROQ_WHISPER_MODEL} | LLM: {GROQ_LLM_MODEL} | Ciclo: {RECORD_DURATION}s")
        self.excel.init_excel()
        print("✅ Pronto.\n")

    def analyze_vad(self, file_path) -> dict | None:
        try:
            y, sr = librosa.load(file_path, sr=16000)
            segs = self.get_speech_timestamps(
                torch.from_numpy(y).float(), self.vad_model, sampling_rate=16000,
            )
            if not segs:
                return None
            total_speech = sum((s["end"] - s["start"]) / sr for s in segs)
            ratio = total_speech / (len(y) / sr)
            if ratio < MIN_SPEECH_RATIO or len(segs) < MIN_SPEECH_SEGS:
                return None
            return {"speech_ratio": ratio, "fragments": len(segs)}
        except Exception as e:
            print(f"  ⚠️  Erro VAD: {e}")
            return None

    def transcribe(self, file_path) -> str:
        try:
            with open(file_path, "rb") as f:
                r = groq_client.audio.transcriptions.create(
                    file=(os.path.basename(file_path), f),
                    model=GROQ_WHISPER_MODEL, language="pt", response_format="text",
                )
            return (r if isinstance(r, str) else str(r)).strip()
        except Exception as e:
            print(f"  ⚠️  Erro Whisper: {e}")
            traceback.print_exc()
            return ""

    def classify(self, text: str, heur: dict) -> list:
        if heur["ad_score"] >= 8 and heur["has_price"] and heur["has_cta"]:
            return [{"anunciante": None, "produto": None, "confianca": "media",
                     "trecho": "", "motivo_curto": "Score heurístico alto (sem LLM)"}]

        nivel = (
            "ATENÇÃO: alta probabilidade de anúncio real." if heur["ad_score"] >= 4
            else "Pode haver anúncio, avalie com cuidado." if heur["ad_score"] >= 2
            else "Score baixo — seja conservador."
        )
        prompt = (
            f"Classifique anúncios publicitários nesta transcrição de rádio brasileiro ({RECORD_DURATION}s).\n"
            f"Pode haver zero, um ou mais anúncios distintos.\n\n"
            f"REGRAS OBRIGATÓRIAS:\n"
            f"1. Anúncio = empresa/marca REAL com intenção de venda, promoção ou CTA.\n"
            f"2. 'anunciante' = NOME DA EMPRESA OU MARCA que paga o anúncio\n"
            f"   (ex: 'Ferreira Decorações', 'Clube Max', 'Farmácia São João').\n"
            f"   Deve aparecer LITERALMENTE no texto; caso contrário use null.\n"
            f"   NUNCA coloque descrições genéricas como 'loja' ou 'empresa'.\n"
            f"3. 'produto' = O QUE está sendo vendido/promovido\n"
            f"   (ex: 'cortinas e tapetes', 'cartão de crédito', 'cursos técnicos').\n"
            f"   NUNCA repita o nome da empresa em 'produto'.\n"
            f"4. REGRA DO VAREJISTA ÂNCORA (CRÍTICA):\n"
            f"   Se o anunciante for um supermercado, mercado, clube de compras, loja ou\n"
            f"   atacado, liste SOMENTE esse estabelecimento como anunciante — mesmo que o\n"
            f"   áudio mencione marcas de produtos (Omo, Guaraná, Nestlé etc.).\n"
            f"   Essas marcas são produtos vendidos pelo varejista, NÃO anunciantes separados.\n"
            f"   Coloque as marcas/produtos mencionados no campo 'produto' do varejista.\n"
            f"   ERRADO: [{{'anunciante':'Clube Max',...}},{{'anunciante':'Omo',...}},{{'anunciante':'Guaraná Antártica',...}}]\n"
            f"   CERTO:  [{{'anunciante':'Clube Max','produto':'bebidas, Omo, Guaraná Antártica',...}}]\n"
            f"5. 'trecho' = trecho literal do áudio que comprova o anúncio (máx 80 chars).\n"
            f"6. Ignore completamente: notícias, locução esportiva, entrevistas,\n"
            f"   conversa casual, auto-promoção da própria rádio, vinhetas sem CTA.\n"
            f"7. Confiança 'alta' SOMENTE se houver CTA explícito E (preço OU telefone).\n"
            f"8. Sem CTA E sem preço/telefone → confiança máxima = 'media'.\n"
            f"9. Telefone ou WhatsApp mencionado após o nome de um anunciante pertence ao\n"
            f"   anúncio DESSE anunciante — NÃO é um anunciante separado. Nunca crie um\n"
            f"   anunciante cujo nome seja um número de telefone ou 'Fone Whats'.\n"
            f"{nivel}\n\n"
            f"Exemplos corretos:\n"
            f'  {{"anunciante":"Ferreira Decorações","produto":"cortinas e tapetes","confianca":"media","trecho":"Ferreira Decorações, qualidade e estilo para sua casa"}}\n'
            f'  {{"anunciante":"Clube Max","produto":"bebidas 900ml, Omo, Guaraná Antártica","confianca":"alta","trecho":"Clube Max a partir de R$ 5,99"}}\n\n'
            f"Texto:\n\"\"\"{text}\"\"\"\n\n"
            f"Responda APENAS JSON válido, sem markdown:\n"
            f'{{"anuncios":[{{"anunciante":"nome literal ou null","produto":"o que é vendido","confianca":"alta|media|baixa","trecho":"trecho literal max80chars"}}]}}\n'
            f"Se não houver anúncio: {{\"anuncios\":[]}}"
        )

        try:
            resp = groq_client.chat.completions.create(
                model=GROQ_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or ""
            try:
                data = json.loads(raw)
            except Exception:
                m = re.search(r"\{.*\}", raw, flags=re.S)
                data = json.loads(m.group(0)) if m else {}

            aprovados = []
            seen_anunciantes: set = set()
            seen_trechos: list = []
            has_strong_anchor = heur["has_cta"] and (heur["has_price"] or heur["has_phone"])
            has_weak_anchor = heur["has_price"] or heur["has_phone"] or heur["has_cta"]

            for ad in (data.get("anuncios") or []):
                if not isinstance(ad, dict):
                    continue

                anunc_raw = (ad.get("anunciante") or "").strip()
                anunciante = None
                if anunc_raw and anunc_raw.lower() not in ("null", "none", "desconhecido", "—", ""):
                    if name_in_text(anunc_raw, text):
                        anunciante = anunc_raw
                    else:
                        print(f"  🚫 Anunciante '{anunc_raw}' não encontrado no texto — descartado.")

                produto = (ad.get("produto") or "").strip() or None
                if produto and produto.lower() in ("null", "none", ""):
                    produto = None
                if produto and anunciante and produto.lower() == anunciante.lower():
                    produto = None

                conf = str(ad.get("confianca", "baixa")).lower().strip()
                if conf not in ("alta", "media", "baixa"):
                    conf = "baixa"
                trecho = (ad.get("trecho") or "")[:80]

                if conf == "alta" and not has_strong_anchor:
                    conf = "media" if has_weak_anchor else "baixa"
                    print(f"  ⬇️  Confiança rebaixada → {conf}")
                elif conf == "media" and not has_weak_anchor and heur["ad_score"] < 4:
                    conf = "baixa"
                    print("  ⬇️  Confiança rebaixada → baixa")

                if not anunciante:
                    if conf in ("baixa", "media"):
                        print(f"  ⛔ Descartado: sem anunciante confirmado (conf={conf}).")
                        continue
                    if conf == "alta" and not has_strong_anchor:
                        print("  ⛔ Descartado: alta sem âncora e sem anunciante.")
                        continue

                chave = (anunciante or "").lower()
                if chave and chave in seen_anunciantes:
                    print(f"  🔁 Anunciante duplicado no ciclo: {chave}")
                    continue
                if chave:
                    seen_anunciantes.add(chave)

                if trecho:
                    if any(len(set(trecho.lower().split()) & set(t.lower().split())) > 4 for t in seen_trechos):
                        print(f"  🔁 Trecho duplicado: {trecho[:40]}...")
                        continue
                    seen_trechos.append(trecho)

                chave_tempo = (anunciante or trecho[:20] or "unknown").lower()
                ultimo = self._recent_ads.get(chave_tempo)
                if ultimo and (br_now() - ultimo).total_seconds() < AD_COOLDOWN_SECONDS:
                    print(f"  🕐 Cooldown ativo para '{chave_tempo}' — ignorando.")
                    continue
                self._recent_ads[chave_tempo] = br_now()

                if conf == "baixa" and heur["ad_score"] >= 6 and anunciante:
                    conf = "media"

                aceito = conf == "alta" or (conf == "media" and heur["ad_score"] >= 3)
                if aceito:
                    aprovados.append({"anunciante": anunciante, "produto": produto,
                                      "confianca": conf, "trecho": trecho})

            retail_ads = [a for a in aprovados if is_retail_anchor(a.get("anunciante", ""), text)]
            nonretail = [a for a in aprovados if not is_retail_anchor(a.get("anunciante", ""), text)]
            if retail_ads and nonretail:
                extra = ", ".join(filter(None, [b.get("anunciante") or b.get("produto") for b in nonretail]))
                for ra in retail_ads:
                    base = ra.get("produto") or ""
                    ra["produto"] = (base + (", " + extra if extra else "")).strip(", ")
                print(f"  🏪 Varejista âncora: {len(nonretail)} marca(s) incorporada(s) como produto.")
                aprovados = retail_ads

            if not aprovados and heur["ad_score"] >= 7 and heur["has_price"] and heur["has_cta"]:
                aprovados.append({"anunciante": None, "produto": None, "confianca": "baixa",
                                  "trecho": "", "motivo_curto": "Detectado por heurística"})
            return aprovados

        except Exception as e:
            print(f"  ⚠️  Erro LLM: {e}")
            return []

    def save_ad(self, station, audio_file, info, index=0) -> str:
        parts = [safe_filename(station), safe_filename(info.get("anunciante") or "Desconhecido")]
        produto = safe_filename(info.get("produto") or "")
        if produto and produto != "Desconhecido":
            parts.append(produto)
        parts.append(br_timestamp())
        if index > 0:
            parts.append(f"ad{index}")
        dest = os.path.join(self.ads_path, "__".join(parts) + ".mp3")
        shutil.copy2(audio_file, dest)
        return dest

    def process_item(self, name, audio_file):
        try:
            vad = self.analyze_vad(audio_file)
            if not vad:
                print(f"  🎵 [{name}] Ignorado (pouca fala)")
                return

            print(f"  🔍 [{name}] Transcrevendo... (speech={vad['speech_ratio']:.0%}, frags={vad['fragments']})")

            full_text = self.transcribe(audio_file)
            full_text = fix_transcription(full_text)
            snippet = full_text[:TRANSCRIPTION_CAP]

            if not snippet:
                print(f"  ⚠️  [{name}] Transcrição vazia.")
                return

            heur = heuristic_score(snippet)
            print(f"  📊 [{name}] ad={heur['ad_score']} nonad={heur['nonad_score']} "
                  f"cta={heur['has_cta']} preço={heur['has_price']} vinheta={heur['is_vinheta']}")

            motivo = should_skip(heur, station_name=name, text=snippet)
            if motivo:
                print(f"  🎵 [{name}] Descartado: {motivo}.")
                return

            print(f"  📝 [{name}] {snippet[:200].replace(chr(10), ' ')!r}")
            anuncios = self.classify(snippet, heur)

            if not anuncios:
                print(f"  🎵 [{name}] Nenhum anúncio detectado.")
                return

            print(f"  📢 [{name}] {len(anuncios)} anúncio(s)!")
            for i, info in enumerate(anuncios, 1):
                marca = info.get("anunciante") or "Desconhecido"
                conf = info.get("confianca", "media")
                print(f"       [{i}] {marca} (conf={conf}) — {info.get('trecho', '')[:80]}")
                saved = self.save_ad(name, audio_file, info, index=i if len(anuncios) > 1 else 0)
                self.excel.append_to_excel(
                    station=name,
                    info=info,
                    audio_file=saved,
                    start_time=self.start_time,
                    session_excel_rows=self._session_excel_rows,
                )
                print(f"       💾 {os.path.basename(saved)}")

        except Exception as e:
            print(f"  ❌ [{name}] Erro: {e}")
            traceback.print_exc()
        finally:
            if os.path.exists(audio_file):
                os.remove(audio_file)

    def run(self):
        print("🚀 Monitoramento iniciado...")
        print(f"   Rádios   : {', '.join(STATIONS.keys())}")
        print(f"   Duração  : {RECORD_DURATION}s | Relatório: {os.path.abspath(self.report_path)}")
        print("   (Ctrl+C para parar)\n")

        self.start_time = br_now()
        print(f"   ⏱️  Sessão iniciada em: {self.start_time.strftime('%d/%m/%Y %H:%M:%S')}\n")

        work_queue = queue.Queue()
        stop_event = threading.Event()
        threads = []

        for name, url in STATIONS.items():
            t = threading.Thread(
                target=recorder_worker,
                args=(name, url, self.audio_path, work_queue, stop_event),
                daemon=True,
                name=f"rec-{name}",
            )
            t.start()
            threads.append(t)

        print(f"  🎙️  {len(threads)} gravadores iniciados.\n")

        try:
            while not stop_event.is_set():
                try:
                    name, audio_file = work_queue.get(timeout=2)
                    print(f"\n{'─' * 60}\n📥 [{name}] Novo áudio — {br_display()}")
                    self.process_item(name, audio_file)
                    work_queue.task_done()
                except queue.Empty:
                    continue
        except KeyboardInterrupt:
            print("\n\n🛑 Encerrando...")
        finally:
            stop_event.set()
            for t in threads:
                t.join(timeout=5)
            self.excel.finalize_session_excel(
                start_time=self.start_time,
                session_excel_rows=self._session_excel_rows,
            )
            print("👋 Encerrado.")
