# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Interface gráfica (Tkinter): mostra o som captado, as batidas e os bits.

Rode com:  python interface.py

Duas threads trabalham juntas:
  - a thread do microfone lê janelas de 10 ms, passa pelo DetectorBatidas e
    pelo MontadorQuadros (os mesmos do receptor de terminal) e coloca
    "eventos" numa fila;
  - a thread da tela (Tkinter) esvazia essa fila a cada 30 ms e desenha.
O Tkinter só pode ser usado pela thread da tela, por isso a fila no meio.
"""

import math
import queue
import threading
import tkinter as tk
from tkinter import ttk

import audio
import metodo1_emissor
import metodo2
from config import DURACAO_JANELA, LIMIAR_MINIMO, TAXA_AMOSTRAGEM
from metodo1_receptor import (BIT_INVALIDO, DetectorBatidas, MontadorQuadros,
                              quadro_integro, relatar_quadro)
from quadro import TAMANHO_DADOS, TAMANHO_QUADRO, bits_para_caractere

INTERVALO_TELA_MS = 30       # de quanto em quanto tempo a tela é redesenhada
HISTORICO_JANELAS = 300      # 300 janelas x 10 ms = 3 s de histórico no gráfico
DB_MINIMO = -60.0            # nível mais baixo mostrado no gráfico (dB em relação ao máximo)
DURACAO_PISCA_MS = 150       # quanto tempo o indicador "BATIDA!" fica aceso
DURACAO_RECEPCAO_M2 = 10.0   # s de gravação ao receber pelo Método 2

COR_FUNDO = "#1e1e1e"
COR_NIVEL = "#4caf50"
COR_BATIDA = "#ff5252"
COR_LIMIAR = "#ffc107"
COR_SUCESSO = "#2e7d32"
COR_FALHA = "#c62828"


def nivel_em_db(nivel: float) -> float:
    """Converte RMS (0 a 1) em decibéis: 1.0 -> 0 dB, 0.001 -> -60 dB."""
    if nivel <= 0:
        return DB_MINIMO
    return max(DB_MINIMO, 20 * math.log10(nivel))


class Aplicacao:
    """Janela principal: medidor de som, quadro atual e quadros recebidos."""

    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        self.eventos: queue.Queue = queue.Queue()
        self.parar_escuta = threading.Event()
        self.thread_escuta: threading.Thread | None = None

        # Histórico do gráfico: (nível, limiar, houve_batida) de cada janela
        self.historico: list[tuple[float, float, bool]] = []
        self.texto_recebido = ""
        self.sucessos = 0
        self.falhas = 0

        raiz.title("Camada Física usando Som")
        raiz.minsize(760, 640)
        self.criar_widgets()
        raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        raiz.after(INTERVALO_TELA_MS, self.atualizar_tela)

    # ------------------------------------------------------------ montagem da tela

    def criar_widgets(self) -> None:
        principal = ttk.Frame(self.raiz, padding=10)
        principal.pack(fill="both", expand=True)

        # --- Controles da escuta
        topo = ttk.Frame(principal)
        topo.pack(fill="x")
        self.botao_escuta = ttk.Button(topo, text="▶ Começar a escutar (Método 1)",
                                       command=self.alternar_escuta)
        self.botao_escuta.pack(side="left")
        ttk.Button(topo, text="Limpar", command=self.limpar).pack(side="left", padx=6)
        self.rotulo_batida = tk.Label(topo, text="  BATIDA!  ", font=("Segoe UI", 14, "bold"),
                                      bg="#444444", fg="#888888")
        self.rotulo_batida.pack(side="right")

        # --- Gráfico do nível do microfone
        ttk.Label(principal, text="Nível do microfone (últimos 3 s) — "
                  "verde: som | vermelho: batida detectada | amarelo: limiar").pack(anchor="w", pady=(10, 0))
        self.grafico = tk.Canvas(principal, height=160, bg=COR_FUNDO, highlightthickness=0)
        self.grafico.pack(fill="x")
        self.rotulo_nivel = ttk.Label(principal, text="Nível: -- dB | limiar: -- dB")
        self.rotulo_nivel.pack(anchor="w")

        # --- Quadro sendo montado: 9 casas
        ttk.Label(principal, text="Quadro sendo recebido (8 bits de dados + paridade):").pack(anchor="w", pady=(10, 0))
        linha_bits = ttk.Frame(principal)
        linha_bits.pack(anchor="w")
        self.casas_bits = []
        for posicao in range(TAMANHO_QUADRO):
            if posicao == TAMANHO_DADOS:
                ttk.Label(linha_bits, text=" | ").pack(side="left")
            casa = tk.Label(linha_bits, text=" ", width=3, font=("Consolas", 20, "bold"),
                            relief="ridge", bg="white")
            casa.pack(side="left", padx=2)
            self.casas_bits.append(casa)
        self.rotulo_bit_aberto = ttk.Label(principal, text="Batidas no bit atual: 0")
        self.rotulo_bit_aberto.pack(anchor="w")

        # --- Quadros recebidos
        ttk.Label(principal, text="Quadros recebidos:").pack(anchor="w", pady=(10, 0))
        self.lista_quadros = tk.Listbox(principal, height=8, font=("Consolas", 11))
        self.lista_quadros.pack(fill="both", expand=True)
        self.rotulo_texto = ttk.Label(principal, text="Texto recebido: ''  (0 sucesso / 0 falha)",
                                      font=("Segoe UI", 11, "bold"))
        self.rotulo_texto.pack(anchor="w", pady=(4, 0))

        # --- Envio
        envio = ttk.LabelFrame(principal, text="Enviar pelo alto-falante", padding=6)
        envio.pack(fill="x", pady=(10, 0))
        self.campo_texto = ttk.Entry(envio, width=30)
        self.campo_texto.insert(0, "Oi")
        self.campo_texto.pack(side="left")
        self.simular_erro = tk.BooleanVar(value=False)
        ttk.Checkbutton(envio, text="Simular erro", variable=self.simular_erro).pack(side="left", padx=6)
        ttk.Button(envio, text="Enviar (Método 1)", command=self.enviar_metodo1).pack(side="left")
        ttk.Button(envio, text="Enviar (Método 2)", command=self.enviar_metodo2).pack(side="left", padx=6)
        ttk.Button(envio, text=f"Receber Método 2 ({DURACAO_RECEPCAO_M2:.0f} s)",
                   command=self.receber_metodo2).pack(side="left")

        self.rotulo_status = ttk.Label(principal, text="Pronto.", foreground="#555555")
        self.rotulo_status.pack(anchor="w", pady=(6, 0))

    # ------------------------------------------------------------ thread do microfone

    def alternar_escuta(self) -> None:
        if self.thread_escuta is not None and self.thread_escuta.is_alive():
            self.parar_escuta.set()
            self.botao_escuta.config(text="▶ Começar a escutar (Método 1)")
            self.rotulo_status.config(text="Escuta parada.")
            return
        self.parar_escuta.clear()
        self.thread_escuta = threading.Thread(target=self.escutar, daemon=True)
        self.thread_escuta.start()
        self.botao_escuta.config(text="■ Parar de escutar")
        self.rotulo_status.config(text="Escutando... medindo o ruído da sala no começo, fique em silêncio.")

    def escutar(self) -> None:
        """Roda na thread do microfone. Mesma lógica de metodo1_receptor.escutar()."""
        detector = DetectorBatidas()
        montador = MontadorQuadros()
        janelas_lidas = 0
        gerador = audio.janelas_do_microfone()
        try:
            for janela in gerador:
                if self.parar_escuta.is_set():
                    break
                instante = janelas_lidas * DURACAO_JANELA
                janelas_lidas += 1

                houve_batida = detector.processar(janela, instante)
                if houve_batida:
                    fechados = montador.adicionar_batida(instante)
                else:
                    fechados = montador.verificar_tempo(instante)

                self.eventos.put(("nivel", audio.rms(janela), detector.limiar(), houve_batida))
                for quadro in fechados:
                    self.eventos.put(("quadro", quadro))
                # cópia da lista: a thread da tela não pode ver a lista mudando
                self.eventos.put(("estado", list(montador.bits), montador.batidas_no_bit))
        except Exception as erro:  # ex.: microfone desconectado
            self.eventos.put(("status", f"Erro no microfone: {erro}"))
        finally:
            gerador.close()  # fecha o stream do sounddevice

    # ------------------------------------------------------------ desenho

    def atualizar_tela(self) -> None:
        """Esvazia a fila de eventos e redesenha. Chamado a cada INTERVALO_TELA_MS."""
        estado = None
        while True:
            try:
                evento = self.eventos.get_nowait()
            except queue.Empty:
                break
            tipo = evento[0]
            if tipo == "nivel":
                self.historico.append(evento[1:])
                if evento[3]:
                    self.piscar_batida()
            elif tipo == "quadro":
                self.mostrar_quadro(evento[1])
            elif tipo == "estado":
                estado = evento  # só o mais recente importa
            elif tipo == "status":
                self.rotulo_status.config(text=evento[1])

        self.historico = self.historico[-HISTORICO_JANELAS:]
        self.desenhar_grafico()
        if estado is not None:
            self.desenhar_quadro_atual(estado[1], estado[2])
        self.raiz.after(INTERVALO_TELA_MS, self.atualizar_tela)

    def altura_no_grafico(self, nivel: float, altura: int) -> float:
        """Posição y no gráfico: 0 dB no topo, DB_MINIMO na base."""
        fracao = (nivel_em_db(nivel) - DB_MINIMO) / -DB_MINIMO
        return altura - fracao * altura

    def desenhar_grafico(self) -> None:
        self.grafico.delete("all")
        largura = self.grafico.winfo_width()
        altura = self.grafico.winfo_height()
        if not self.historico:
            return
        largura_barra = largura / HISTORICO_JANELAS
        for indice, (nivel, _, batida) in enumerate(self.historico):
            x = indice * largura_barra
            y = self.altura_no_grafico(nivel, altura)
            cor = COR_BATIDA if batida else COR_NIVEL
            # batida ganha barra mais larga para ficar visível
            self.grafico.create_rectangle(x, y, x + max(largura_barra, 3 if batida else 1), altura,
                                          fill=cor, outline="")

        nivel, limiar, _ = self.historico[-1]
        y_limiar = self.altura_no_grafico(limiar, altura)
        self.grafico.create_line(0, y_limiar, largura, y_limiar, fill=COR_LIMIAR, dash=(4, 2))
        self.rotulo_nivel.config(text=f"Nível: {nivel_em_db(nivel):.0f} dB | "
                                      f"limiar: {nivel_em_db(limiar):.0f} dB "
                                      f"(mínimo {nivel_em_db(LIMIAR_MINIMO):.0f} dB)")

    def piscar_batida(self) -> None:
        self.rotulo_batida.config(bg=COR_BATIDA, fg="white")
        self.raiz.after(DURACAO_PISCA_MS,
                        lambda: self.rotulo_batida.config(bg="#444444", fg="#888888"))

    def desenhar_quadro_atual(self, bits: list[int], batidas_no_bit: int) -> None:
        for posicao, casa in enumerate(self.casas_bits):
            if posicao < len(bits):
                bit = bits[posicao]
                casa.config(text="?" if bit == BIT_INVALIDO else str(bit), bg="#bbdefb")
            elif posicao == len(bits) and batidas_no_bit > 0:
                casa.config(text="…", bg="#fff59d")  # bit ainda aberto (esperando silêncio)
            else:
                casa.config(text=" ", bg="white")
        self.rotulo_bit_aberto.config(text=f"Batidas no bit atual: {batidas_no_bit} "
                                           f"(1 batida = 0, 2 batidas = 1)")

    def mostrar_quadro(self, quadro: list[int]) -> None:
        self.lista_quadros.insert("end", relatar_quadro(quadro))
        if quadro_integro(quadro):
            self.sucessos += 1
            self.texto_recebido += bits_para_caractere(quadro[:TAMANHO_DADOS])
            cor = COR_SUCESSO
        else:
            self.falhas += 1
            cor = COR_FALHA
        self.lista_quadros.itemconfig("end", foreground=cor)
        self.lista_quadros.see("end")
        self.atualizar_texto_recebido()

    def atualizar_texto_recebido(self) -> None:
        self.rotulo_texto.config(text=f"Texto recebido: {self.texto_recebido!r}  "
                                      f"({self.sucessos} sucesso / {self.falhas} falha)")

    def limpar(self) -> None:
        self.lista_quadros.delete(0, "end")
        self.texto_recebido = ""
        self.sucessos = 0
        self.falhas = 0
        self.atualizar_texto_recebido()

    # ------------------------------------------------------------ envio / Método 2

    def em_segundo_plano(self, tarefa, mensagem: str) -> None:
        """Roda `tarefa` numa thread para a janela não travar enquanto toca/grava."""
        self.rotulo_status.config(text=mensagem)

        def executar():
            try:
                resultado = tarefa()
            except Exception as erro:
                resultado = f"Erro: {erro}"
            self.eventos.put(("status", resultado))

        threading.Thread(target=executar, daemon=True).start()

    def enviar_metodo1(self) -> None:
        texto = self.campo_texto.get()
        try:
            quadros = metodo1_emissor.texto_para_quadros(texto)
        except ValueError:
            self.rotulo_status.config(text="O Método 1 só aceita caracteres ASCII (sem acentos).")
            return
        if not quadros:
            return
        if self.simular_erro.get():
            quadros[0] = metodo1_emissor.inverter_bit(quadros[0], 0)

        def tarefa():
            instantes = metodo1_emissor.quadros_para_instantes(quadros)
            audio.tocar(metodo1_emissor.sintetizar_batidas(instantes))
            return f"Método 1: {len(quadros)} quadro(s) enviado(s)."

        self.em_segundo_plano(tarefa, f"Método 1: tocando {len(quadros)} quadro(s)...")

    def enviar_metodo2(self) -> None:
        dados = self.campo_texto.get().encode("utf-8")
        erro = self.simular_erro.get()

        def tarefa():
            sinal = metodo2.modular(dados, erro)
            audio.tocar(sinal)
            return (f"Método 2: {len(dados)} byte(s) em {len(sinal) / TAXA_AMOSTRAGEM:.2f} s "
                    f"(taxa teórica {metodo2.taxa_teorica_bps():.0f} bps).")

        self.em_segundo_plano(tarefa, "Método 2: tocando...")

    def receber_metodo2(self) -> None:
        if self.thread_escuta is not None and self.thread_escuta.is_alive():
            self.alternar_escuta()  # libera o microfone

        def tarefa():
            sinal = audio.gravar(DURACAO_RECEPCAO_M2)
            dados, crc_ok = metodo2.demodular(sinal)
            return "Método 2: " + metodo2.relatar_mensagem(dados, crc_ok)

        self.em_segundo_plano(tarefa, f"Método 2: gravando {DURACAO_RECEPCAO_M2:.0f} s... "
                                      "comece a transmissão no outro computador.")

    def fechar(self) -> None:
        self.parar_escuta.set()
        self.raiz.destroy()


if __name__ == "__main__":
    janela_principal = tk.Tk()
    Aplicacao(janela_principal)
    janela_principal.mainloop()
