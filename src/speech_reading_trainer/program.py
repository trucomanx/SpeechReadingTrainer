#!/usr/bin/python3
import sys
import os
import io
import signal
import string
import threading
import subprocess

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QTextEdit, QLabel,
    QProgressBar, QFileDialog, QVBoxLayout, QWidget, QHBoxLayout,
    QSizePolicy, QAction, QMessageBox, QListView, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QStringListModel
from PyQt5.QtGui import QIcon, QDesktopServices

import speech_recognition as sr
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play


import speech_reading_trainer.about as about
import speech_reading_trainer.modules.configure as configure 
from speech_reading_trainer.modules.resources import resource_path
from speech_reading_trainer.modules.wabout    import show_about_window
from speech_reading_trainer.desktop import create_desktop_file, create_desktop_directory, create_desktop_menu

# ---------- Path to config file ----------
CONFIG_PATH = os.path.join( os.path.expanduser("~"),
                            ".config", 
                            about.__package__, 
                            "config.json" )

DEFAULT_CONTENT={   
    # Toolbar
    "toolbar_configure": "Configure",
    "toolbar_configure_tooltip": "Open the configuration JSON file to customize the GUI texts and settings",
    "toolbar_about": "About",
    "toolbar_about_tooltip": "Show information about this program",
    "toolbar_coffee": "Coffee",
    "toolbar_coffee_tooltip": "Support the developer (TrucomanX)",

    # Window
    "window_width": 1024,
    "window_height": 400,

    # Main buttons and labels
    "button_open_file": "Select Text File",
    "button_open_file_tooltip": "Select a text file to start reading practice",

    "label_progress": "Progress:",
    "label_progress_tooltip": "Shows how many sentences have been completed",

    "label_accuracy": "Current Accuracy: 0.00%",
    "label_accuracy_tooltip": "Displays accumulated word accuracy percentage",

    "label_current_sentence": "Current Sentence:",
    "label_current_sentence_tooltip": "Sentence you must read aloud",

    "button_tts": "Listen (TTS)",
    "button_tts_tooltip": "Play the sentence using text-to-speech",

    "button_record": "Record",
    "button_record_tooltip": "Start recording your voice",

    "button_stop": "Stop Recording",
    "button_stop_tooltip": "Stop the current voice recording",

    "button_play_recording": "Play Recording",
    "button_play_recording_tooltip": "Play your recorded voice",

    "label_transcription": "Transcription:",
    "label_transcription_tooltip": "Automatic speech recognition result",

    "button_evaluate": "Evaluate / Next",
    "button_evaluate_tooltip": "Evaluate pronunciation and move to next sentence",

    "file_dialog_title": "Open Text File",
    "file_dialog_filter": "Text Files (*.txt)",

    "button_save_missing_words": "Save Missing Words",
    "button_delete_missing_words": "Delete Missing Words",
    
    "msg_confirm": "Confirm",
    "msg_delete_words": "Do you really want to delete all the accumulated words?",
    "msg_save_missing_words": "Save Missing Words",

    "final_message": "Finished! Final Accuracy: {value:.2f}%"
}

configure.verify_default_config(CONFIG_PATH, default_content=DEFAULT_CONTENT)
CONFIG = configure.load_config(CONFIG_PATH)

# ---------------------------------------

# ==========================
# Funções auxiliares
# ==========================

def ler_e_separar_texto(caminho_arquivo, tamanho_maximo=125, separadores=None):
    if separadores is None:
        separadores = ["\n\n", ".", ";", ",", "?"]

    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        texto = f.read()

    def separar_por(texto, sep_list):
        if not sep_list:
            return [texto.strip()]
        sep = sep_list[0]
        partes = texto.split(sep)
        resultado = []
        for i, parte in enumerate(partes):
            if i < len(partes) - 1:
                parte = parte.strip() + sep
            else:
                parte = parte.strip()
            resultado.extend(separar_por(parte, sep_list[1:]))
        return [r for r in resultado if r]

    frases_iniciais = separar_por(texto, separadores)
    frases_final = []

    for frase in frases_iniciais:
        frase = frase.replace("\n", " ").strip()
        if len(frase) <= tamanho_maximo:
            frases_final.append(frase)
        else:
            partes_virgula = [p.strip() + ("," if i < len(frase.split(",")) - 1 else "")
                               for i, p in enumerate(frase.split(",")) if p.strip()]
            for pv in partes_virgula:
                if len(pv) <= tamanho_maximo:
                    frases_final.append(pv)
                else:
                    palavras = pv.split()
                    temp = ""
                    for p in palavras:
                        if len(temp) + len(p) + 1 <= tamanho_maximo:
                            temp += (" " if temp else "") + p
                        else:
                            frases_final.append(temp)
                            temp = p
                    if temp:
                        frases_final.append(temp)
    return frases_final

def comparar_frases_bag_of_words(original, transcrito):
    trad = str.maketrans("", "", string.punctuation)
    original_words = set(original.translate(trad).lower().split())
    transcrito_words = set(transcrito.translate(trad).lower().split())
    acertos = len(original_words & transcrito_words)
    total = len(original_words)
    return acertos, total


def palavras_faltantes(original, transcrito):
    """
    Retorna as palavras que estão na frase original
    mas não apareceram na transcrição.
    """
    trad = str.maketrans("", "", string.punctuation)
    original_words = set(original.translate(trad).lower().split())
    transcrito_words = set(transcrito.translate(trad).lower().split())
    return original_words - transcrito_words


def gravar_audio(destino):
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Gravando...")
        audio = r.listen(source)
        print("Gravação finalizada.")
    with open(destino, "wb") as f:
        f.write(audio.get_wav_data())


def transcrever_audio(caminho_audio):
    r = sr.Recognizer()
    with sr.AudioFile(caminho_audio) as source:
        audio = r.record(source)
    try:
        texto = r.recognize_google(audio)
        return texto
    except:
        return ""

def tts_play(texto, idioma="en", fator=1.0):
    mp3_fp = io.BytesIO()
    tts = gTTS(text=texto, lang=idioma)
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    audio = AudioSegment.from_file(mp3_fp, format="mp3")
    if fator != 1.0:
        audio = audio.speedup(playback_speed=fator)
    threading.Thread(target=lambda: play(audio), daemon=True).start()

def transcricao_com_cores(transcrito, original):
    trad = str.maketrans("", "", string.punctuation)
    orig_words_set = set([w.translate(trad).lower() for w in original.split()])
    words = transcrito.split()
    html = ""
    for w in words:
        w_clean = w.translate(trad).lower()
        if w_clean in orig_words_set:
            html += f'<span style="color:black">{w}</span> '
        else:
            html += f'<span style="color:red">{w}</span> '
    return html.strip()


# ==========================
# Main Window
# ==========================

class SpeechReadingTrainer(QMainWindow):

    transcricao_pronta = pyqtSignal(str)
    grava_finalizada = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle(about.__program_name__)
        self.resize(CONFIG["window_width"], CONFIG["window_height"])

        ## Icon
        # Get base directory for icons
        self.icon_path = resource_path("icons", "logo.png")
        self.setWindowIcon(QIcon(self.icon_path)) 

        self.frases = []
        self.index_frase = 0
        self.total_palavras = 0
        self.total_acertos = 0
        self.audio_path = "recorded.wav"
        self.ultima_transcricao = ""

        self.transcricao_pronta.connect(self.atualizar_transcricao)
        self.grava_finalizada.connect(self.gravacao_finalizada)

        # SET acumulativo de palavras erradas
        self.palavras_erradas = set()
        self.model_palavras = QStringListModel()

        self._create_toolbar()

        # ================= Layout Principal Horizontal =================
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        # Botão abrir arquivo
        self.btn_abrir = QPushButton(CONFIG["button_open_file"])
        self.btn_abrir.setIcon(QIcon.fromTheme("document-send"))
        self.btn_abrir.setToolTip(CONFIG["button_open_file_tooltip"])
        self.btn_abrir.clicked.connect(self.abrir_arquivo)
        layout.addWidget(self.btn_abrir)

        # Barra de progresso e acurácia
        self.label_progresso = QLabel(CONFIG["label_progress"])
        self.label_progresso.setToolTip(CONFIG["label_progress_tooltip"])
        layout.addWidget(self.label_progresso)

        self.progress = QProgressBar()
        self.progress.setToolTip(CONFIG["label_progress_tooltip"])
        layout.addWidget(self.progress)

        self.label_acuracia = QLabel(CONFIG["label_accuracy"])
        self.label_acuracia.setToolTip(CONFIG["label_accuracy_tooltip"])
        layout.addWidget(self.label_acuracia)

        # Frase atual
        self.label_sentence = QLabel(CONFIG["label_current_sentence"])
        self.label_sentence.setToolTip(CONFIG["label_current_sentence_tooltip"])
        layout.addWidget(self.label_sentence)

        self.text_frase = QTextEdit()
        self.text_frase.setReadOnly(True)
        self.text_frase.setToolTip(CONFIG["label_current_sentence_tooltip"])
        layout.addWidget(self.text_frase)

        # Botão TTS
        self.btn_tts = QPushButton(CONFIG["button_tts"])
        self.btn_tts.setIcon(QIcon.fromTheme("audio-volume-high"))
        self.btn_tts.setToolTip(CONFIG["button_tts_tooltip"])
        self.btn_tts.setEnabled(False)
        self.btn_tts.clicked.connect(self.ouvir_tts)
        layout.addWidget(self.btn_tts)

        # Botões gravação
        h_layout = QHBoxLayout()

        self.btn_gravar = QPushButton(CONFIG["button_record"])
        self.btn_gravar.setIcon(QIcon.fromTheme("media-record"))
        self.btn_gravar.setToolTip(CONFIG["button_record_tooltip"])
        self.btn_gravar.setEnabled(False)
        self.btn_gravar.clicked.connect(self.gravar)
        h_layout.addWidget(self.btn_gravar)

        self.btn_parar = QPushButton(CONFIG["button_stop"])
        self.btn_parar.setIcon(QIcon.fromTheme("media-playback-stop"))
        self.btn_parar.setToolTip(CONFIG["button_stop_tooltip"])
        self.btn_parar.setEnabled(False)
        self.btn_parar.clicked.connect(self.parar_gravacao)
        h_layout.addWidget(self.btn_parar)

        self.btn_ouvir = QPushButton(CONFIG["button_play_recording"])
        self.btn_ouvir.setIcon(QIcon.fromTheme("audio-volume-high"))
        self.btn_ouvir.setToolTip(CONFIG["button_play_recording_tooltip"])
        self.btn_ouvir.setEnabled(False)
        self.btn_ouvir.clicked.connect(self.ouvir_gravado)
        h_layout.addWidget(self.btn_ouvir)

        layout.addLayout(h_layout)

        # Texto transcrito
        self.label_trans = QLabel(CONFIG["label_transcription"])
        self.label_trans.setToolTip(CONFIG["label_transcription_tooltip"])
        layout.addWidget(self.label_trans)

        self.text_transcrito = QTextEdit()
        self.text_transcrito.setReadOnly(True)
        self.text_transcrito.setToolTip(CONFIG["label_transcription_tooltip"])
        layout.addWidget(self.text_transcrito)

        # Botão Avaliar
        self.btn_avaliar = QPushButton(CONFIG["button_evaluate"])
        self.btn_avaliar.setIcon(QIcon.fromTheme("document-page-setup"))
        self.btn_avaliar.setToolTip(CONFIG["button_evaluate_tooltip"])
        self.btn_avaliar.setEnabled(False)
        self.btn_avaliar.clicked.connect(self.avaliar)
        layout.addWidget(self.btn_avaliar)

        # ----- Painel direito -----
        self.list_view = QListView()
        self.list_view.setModel(self.model_palavras)
        right_layout.addWidget(self.list_view)


        self.btn_salvar_lista = QPushButton(CONFIG["button_save_missing_words"])
        self.btn_salvar_lista.setIcon(QIcon.fromTheme("document-save"))
        self.btn_salvar_lista.clicked.connect(self.salvar_palavras_erradas)
        right_layout.addWidget(self.btn_salvar_lista)
        
        self.btn_delete_lista = QPushButton(CONFIG["button_delete_missing_words"])
        self.btn_delete_lista.setIcon(QIcon.fromTheme("edit-delete"))
        self.btn_delete_lista.clicked.connect(self.apagar_lista_palavras)
        right_layout.addWidget(self.btn_delete_lista)

        # ----- Montagem final -----
        # ----- Montagem final com QSplitter -----

        splitter = QSplitter(Qt.Horizontal)

        # Widget esquerdo
        left_widget = QWidget()
        left_widget.setLayout(layout)

        # Widget direito
        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)

        # tamanho inicial (opcional)
        splitter.setSizes([800, 200])

        main_layout.addWidget(splitter)

        central_widget.setLayout(main_layout)


    def _create_toolbar(self):
        self.toolbar = self.addToolBar("Main")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        # Adicionar o espaçador
        self.toolbar_spacer = QWidget()
        self.toolbar_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toolbar.addWidget(self.toolbar_spacer)
        
        #
        self.configure_action = QAction(QIcon.fromTheme("document-properties"), 
                                        CONFIG["toolbar_configure"], 
                                        self)
        self.configure_action.setToolTip(CONFIG["toolbar_configure_tooltip"])
        self.configure_action.triggered.connect(self.open_configure_editor)
        self.toolbar.addAction(self.configure_action)
        
        #
        self.about_action = QAction(QIcon.fromTheme("help-about"), 
                                    CONFIG["toolbar_about"], 
                                    self)
        self.about_action.setToolTip(CONFIG["toolbar_about_tooltip"])
        self.about_action.triggered.connect(self.open_about)
        self.toolbar.addAction(self.about_action)
        
        # Coffee
        self.coffee_action = QAction(   QIcon.fromTheme("emblem-favorite"), 
                                        CONFIG["toolbar_coffee"], 
                                        self)
        self.coffee_action.setToolTip(CONFIG["toolbar_coffee_tooltip"])
        self.coffee_action.triggered.connect(self.on_coffee_action_click)
        self.toolbar.addAction(self.coffee_action)

        # Conectar ao sinal de mudança de orientação
        self.toolbar.orientationChanged.connect(self.on_update_spacer_policy)
        self.on_update_spacer_policy()

    def apagar_lista_palavras(self):

        resposta = QMessageBox.question(
            self,
            CONFIG["msg_confirm"],
            CONFIG["msg_delete_words"],
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if resposta == QMessageBox.Yes:
            self.palavras_erradas.clear()
            self.atualizar_lista_palavras()
        
    def on_update_spacer_policy(self):
        """Atualiza a política do espaçador baseado na orientação da toolbar"""
        if self.toolbar.orientation() == Qt.Horizontal:
            # Horizontal: expande na largura
            self.toolbar_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        else:
            # Vertical: expande na altura
            self.toolbar_spacer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def _open_file_in_text_editor(self, filepath):
        if os.name == 'nt':  # Windows
            os.startfile(filepath)
        elif os.name == 'posix':  # Linux/macOS
            subprocess.run(['xdg-open', filepath])
            
    def open_configure_editor(self):
        self._open_file_in_text_editor(CONFIG_PATH)

    def open_about(self):
        data={
            "version": about.__version__,
            "package": about.__package__,
            "program_name": about.__program_name__,
            "author": about.__author__,
            "email": about.__email__,
            "description": about.__description__,
            "url_source": about.__url_source__,
            "url_doc": about.__url_doc__,
            "url_funding": about.__url_funding__,
            "url_bugs": about.__url_bugs__
        }
        show_about_window(data,self.icon_path)

    def on_coffee_action_click(self):
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/trucomanx"))
        
    # ==========================
    # Funções
    # ==========================

    def abrir_arquivo(self):
        arquivo, _ = QFileDialog.getOpenFileName(
            self, 
            CONFIG["file_dialog_title"], 
            "", 
            CONFIG["file_dialog_filter"]
        )
        if arquivo:
            self.ultima_transcricao = ""
            
            # Reset estatísticas (mas NÃO as palavras erradas)
            self.total_acertos = 0
            self.total_palavras = 0
            self.atualizar_acuracia()

            self.frases = ler_e_separar_texto(arquivo)
            self.index_frase = 0
            
            if not self.frases:
                QMessageBox.warning(self, "Warning", "The selected file has no valid sentences.")
                return
            
            self.progress.setMaximum(len(self.frases))
            self.progress.setValue(0)

            self.text_frase.setText(self.frases[self.index_frase])
            
            self.btn_tts.setEnabled(True)
            self.btn_gravar.setEnabled(True)
            self.btn_parar.setEnabled(True)
            self.btn_ouvir.setEnabled(True)
            self.btn_avaliar.setEnabled(True)

    def ouvir_tts(self):
        frase = self.frases[self.index_frase]
        tts_play(frase)

    def gravar(self):
        self.btn_gravar.setEnabled(False)
        self.btn_parar.setEnabled(True)
        threading.Thread(target=self._gravar_thread, daemon=True).start()

    def _gravar_thread(self):
        gravar_audio(self.audio_path)
        frase = self.frases[self.index_frase]
        self.ultima_transcricao = transcrever_audio(self.audio_path)
        html = transcricao_com_cores(self.ultima_transcricao, frase)
        self.transcricao_pronta.emit(html)
        self.grava_finalizada.emit()

    def atualizar_transcricao(self, html):
        self.text_transcrito.setHtml(html)

    def gravacao_finalizada(self):
        self.btn_gravar.setEnabled(True)
        self.btn_parar.setEnabled(False)
        self.btn_ouvir.setEnabled(True)

    def parar_gravacao(self):
        self.btn_gravar.setEnabled(True)
        self.btn_parar.setEnabled(False)

    def ouvir_gravado(self):
        if os.path.exists(self.audio_path):
            audio = AudioSegment.from_wav(self.audio_path)
            threading.Thread(target=lambda: play(audio), daemon=True).start()

    def avaliar(self):
        if not os.path.exists(self.audio_path):
            return

        frase = self.frases[self.index_frase]
        transcrito = self.ultima_transcricao
        if not self.ultima_transcricao:
            return

        # Exibe transcrição colorida imediatamente
        html = transcricao_com_cores(transcrito, frase)
        self.text_transcrito.setHtml(html)

        # Atualiza acertos
        acertos, total = comparar_frases_bag_of_words(frase, transcrito)
        self.total_acertos += acertos
        self.total_palavras += total
        self.atualizar_acuracia()

        faltantes = palavras_faltantes(frase, transcrito)
        self.palavras_erradas.update(faltantes)
        self.atualizar_lista_palavras()

        # Avança para próxima frase
        self.index_frase += 1
        self.progress.setValue(self.index_frase)

        if self.index_frase < len(self.frases):
            self.text_frase.setText(self.frases[self.index_frase])
            self.text_transcrito.clear()
        else:
            precisao = (self.total_acertos / self.total_palavras) * 100 if self.total_palavras else 0

            mensagem_final = CONFIG["final_message"].format(value=precisao)

            msg = QMessageBox(self)
            msg.setWindowTitle(about.__program_name__)
            msg.setText(mensagem_final)

            icon = QIcon()
            
            # Ícone customizado do tema
            if   precisao>=83.3333:
                icon = QIcon.fromTheme("trophy-gold")
            elif precisao>=66.6667:
                icon = QIcon.fromTheme("trophy-silver")
            elif precisao>=50:
                icon = QIcon.fromTheme("trophy-bronze")
            
            if not icon.isNull():
                msg.setIconPixmap(icon.pixmap(64, 64))
            else:
                msg.setIcon(QMessageBox.Information)  # fallback

            msg.exec_()

            self.text_frase.setText(mensagem_final)
            self.text_transcrito.clear()

            self.btn_tts.setEnabled(False)
            self.btn_gravar.setEnabled(False)
            self.btn_parar.setEnabled(False)
            self.btn_ouvir.setEnabled(False)
            self.btn_avaliar.setEnabled(False)

    def atualizar_lista_palavras(self):
        lista_ordenada = sorted(self.palavras_erradas)
        self.model_palavras.setStringList(lista_ordenada)

    def salvar_palavras_erradas(self):
        if not self.palavras_erradas:
            return
        
        caminho, _ = QFileDialog.getSaveFileName(
            self,
            CONFIG["msg_save_missing_words"],
            "",
            "Text Files (*.txt)"
        )

        if caminho:
            with open(caminho, "w", encoding="utf-8") as f:
                for palavra in sorted(self.palavras_erradas):
                    f.write(palavra + "\n")

    def atualizar_acuracia(self):
        perc = (self.total_acertos / self.total_palavras) * 100 if self.total_palavras else 0
        self.label_acuracia.setText(f"Current Accuracy: {perc:.2f}%")

# ==========================
# Executar aplicação
# ==========================
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    '''
    create_desktop_directory()    
    create_desktop_menu()
    create_desktop_file(os.path.join("~",".local","share","applications"), 
                        program_name=about.__program_name__)
    
    for n in range(len(sys.argv)):
        if sys.argv[n] == "--autostart":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file(os.path.join("~",".config","autostart"), 
                                overwrite=True, 
                                program_name=about.__program_name__)
            return
        if sys.argv[n] == "--applications":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file(os.path.join("~",".local","share","applications"), 
                                overwrite=True, 
                                program_name=about.__program_name__)
            return
    '''
    
    app = QApplication(sys.argv)
    app.setApplicationName(about.__package__)

    janela = SpeechReadingTrainer()
    janela.show()

    sys.exit(app.exec_())
