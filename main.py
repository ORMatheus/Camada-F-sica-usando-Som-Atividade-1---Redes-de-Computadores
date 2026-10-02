# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Ponto de entrada do programa: Emissor e Receptor dos dois métodos.

Uso pela linha de comando (exemplos):
    python main.py m1-enviar "Oi" [--guiado] [--erro]
    python main.py m1-receber
    python main.py m1-simular "Oi" [--erro] [--ruido 0.02]
    python main.py m2-enviar "Olá, mundo" [--erro]
    python main.py m2-receber [--duracao 10]
    python main.py m2-simular "Olá, mundo" [--erro] [--ruido 0.02]
Sem argumentos, abre um menu interativo com as mesmas opções.

Este arquivo só lê as opções e chama os módulos; a lógica fica neles.
"simular" faz emissor -> ruído -> receptor no próprio computador, sem
microfone nem alto-falante (útil para o vídeo e para testar sem hardware).
"""

import argparse

import numpy as np

import metodo1_emissor
import metodo1_receptor
import metodo2
from config import TAXA_AMOSTRAGEM
from quadro import TAMANHO_DADOS, bits_para_caractere

RUIDO_PADRAO = 0.02         # desvio padrão do ruído gaussiano somado na simulação
DURACAO_RECEPCAO_M2 = 10.0  # s de gravação do receptor do Método 2
SILENCIO_SIMULACAO = 0.5    # s de silêncio antes e depois do sinal do Método 2


# ---------------------------------------------------------------- Método 1

def adicionar_ruido(sinal: np.ndarray, desvio: float) -> np.ndarray:
    """Soma ruído gaussiano ao sinal (imita o ruído de fundo da sala)."""
    gerador = np.random.default_rng()
    ruido = gerador.normal(0.0, desvio, len(sinal))
    return (sinal + ruido).astype(np.float32)


def simular_metodo1(texto: str, simular_erro: bool, desvio_ruido: float) -> None:
    """Loopback do Método 1: quadros -> batidas sintetizadas -> ruído -> receptor."""
    quadros = metodo1_emissor.texto_para_quadros(texto)
    if simular_erro:
        quadros[0] = metodo1_emissor.inverter_bit(quadros[0])
        print("Simulando erro: 1 bit de dados do 1º quadro foi invertido depois da paridade.")

    instantes = metodo1_emissor.quadros_para_instantes(quadros)
    sinal = metodo1_emissor.sintetizar_batidas(instantes)
    sinal = adicionar_ruido(sinal, desvio_ruido)
    duracao = len(sinal) / TAXA_AMOSTRAGEM
    print(f"Enviando {len(quadros)} quadro(s), {len(instantes)} batidas, "
          f"{duracao:.1f} s de áudio, ruído com desvio {desvio_ruido}.\n")

    recebidos = metodo1_receptor.decodificar_audio(sinal)

    texto_recebido = ""
    sucessos = 0
    for quadro in recebidos:
        print(metodo1_receptor.relatar_quadro(quadro))
        # quadro_integro, e não validar_quadro: só ela recusa o bit inválido (-1)
        if metodo1_receptor.quadro_integro(quadro):
            sucessos += 1
            texto_recebido += bits_para_caractere(quadro[:TAMANHO_DADOS])
        else:
            texto_recebido += "?"  # marca a posição do caractere perdido

    falhas = len(recebidos) - sucessos
    # Quadro que sumiu no ruído também é falha (na simulação sabemos quantos saíram)
    perdidos = len(quadros) - len(recebidos)
    if perdidos > 0:
        print(f"[FALHA DE TRANSMISSÃO] {perdidos} quadro(s) enviado(s) não foram detectados")
        falhas += perdidos

    print(f"\nTexto recebido: {texto_recebido!r}")
    print(f"Quadros enviados: {len(quadros)}   recebidos: {len(recebidos)}")
    print(f"Resumo: {sucessos} sucesso(s) / {falhas} falha(s)")


# ---------------------------------------------------------------- Método 2

def simular_metodo2(texto: str, simular_erro: bool, desvio_ruido: float) -> None:
    """Loopback do Método 2: modula -> silêncio + ruído -> demodula."""
    dados = texto.encode("utf-8")
    sinal = metodo2.modular(dados, simular_erro)
    if simular_erro:
        print("Simulando erro: 1 bit dos dados foi invertido depois do cálculo do CRC.")

    # silêncio antes e depois: o receptor precisa achar o início sozinho
    silencio = np.zeros(int(SILENCIO_SIMULACAO * TAXA_AMOSTRAGEM), dtype=np.float32)
    sinal = np.concatenate([silencio, sinal, silencio])
    sinal = adicionar_ruido(sinal, desvio_ruido)

    print(f"Mensagem: {len(dados)} byte(s)   taxa teórica: {metodo2.taxa_teorica_bps():.1f} bps")
    print(f"Duração do sinal: {len(sinal) / TAXA_AMOSTRAGEM:.2f} s   "
          f"ruído com desvio {desvio_ruido}\n")

    recebidos, crc_ok = metodo2.demodular(sinal)
    # mesma linha de SUCESSO/FALHA que o receptor de verdade (metodo2.receber) mostra
    print(metodo2.relatar_mensagem(recebidos, crc_ok))


# ---------------------------------------------------------------- Comandos

COMANDOS_COM_TEXTO = ("m1-enviar", "m1-simular", "m2-enviar", "m2-simular")


def executar(comando: str, texto: str = "", guiado: bool = False, erro: bool = False,
             ruido: float = RUIDO_PADRAO, duracao: float = DURACAO_RECEPCAO_M2) -> None:
    """Executa um comando; usado tanto pela linha de comando quanto pelo menu."""
    # Confere a entrada antes de começar, para mostrar uma mensagem clara
    if comando in COMANDOS_COM_TEXTO and texto == "":
        print("Erro na entrada: o texto está vazio.")
        return
    if ruido < 0:
        print("Erro na entrada: o desvio padrão do ruído não pode ser negativo.")
        return
    if duracao <= 0:
        print("Erro na entrada: a duração da gravação precisa ser maior que zero.")
        return

    try:
        if comando == "m1-enviar":
            metodo1_emissor.transmitir_texto(texto, guiado=guiado, simular_erro=erro)
        elif comando == "m1-receber":
            metodo1_receptor.escutar()
        elif comando == "m1-simular":
            simular_metodo1(texto, erro, ruido)
        elif comando == "m2-enviar":
            metodo2.transmitir_texto(texto, simular_erro=erro)
        elif comando == "m2-receber":
            metodo2.receber(duracao)
        elif comando == "m2-simular":
            simular_metodo2(texto, erro, ruido)
    except ValueError as erro_de_entrada:
        # ex.: caractere fora da tabela ASCII no Método 1
        print(f"Erro na entrada: {erro_de_entrada}")
        if comando.startswith("m1"):
            print("O Método 1 só aceita caracteres ASCII (sem acentos nem ç).")


def criar_parser() -> argparse.ArgumentParser:
    """Define os subcomandos e as opções aceitas na linha de comando."""
    parser = argparse.ArgumentParser(
        description="Camada Física usando Som: Emissor e Receptor acústicos.")
    subcomandos = parser.add_subparsers(dest="comando")

    m1_enviar = subcomandos.add_parser("m1-enviar", help="Método 1: envia texto por batidas")
    m1_enviar.add_argument("texto", help="mensagem a transmitir (use aspas se tiver espaços)")
    m1_enviar.add_argument("--guiado", action="store_true",
                           help="mostra na tela quando uma pessoa deve bater (sem alto-falante)")
    m1_enviar.add_argument("--erro", action="store_true", help="inverte 1 bit do 1º quadro")

    subcomandos.add_parser("m1-receber", help="Método 1: escuta batidas pelo microfone")

    m1_simular = subcomandos.add_parser("m1-simular", help="Método 1: teste sem microfone")
    m1_simular.add_argument("texto", help="mensagem a transmitir (use aspas se tiver espaços)")
    m1_simular.add_argument("--erro", action="store_true", help="inverte 1 bit do 1º quadro")
    m1_simular.add_argument("--ruido", type=float, default=RUIDO_PADRAO,
                            help=f"desvio padrão do ruído (padrão {RUIDO_PADRAO})")

    m2_enviar = subcomandos.add_parser("m2-enviar", help="Método 2: envia texto por MFSK")
    m2_enviar.add_argument("texto", help="mensagem a transmitir (use aspas se tiver espaços)")
    m2_enviar.add_argument("--erro", action="store_true", help="inverte 1 bit dos dados")

    m2_receber = subcomandos.add_parser("m2-receber", help="Método 2: grava e decodifica")
    m2_receber.add_argument("--duracao", type=float, default=DURACAO_RECEPCAO_M2,
                            help=f"segundos de gravação (padrão {DURACAO_RECEPCAO_M2})")

    m2_simular = subcomandos.add_parser("m2-simular", help="Método 2: teste sem microfone")
    m2_simular.add_argument("texto", help="mensagem a transmitir (use aspas se tiver espaços)")
    m2_simular.add_argument("--erro", action="store_true", help="inverte 1 bit dos dados")
    m2_simular.add_argument("--ruido", type=float, default=RUIDO_PADRAO,
                            help=f"desvio padrão do ruído (padrão {RUIDO_PADRAO})")
    return parser


# ---------------------------------------------------------------- Menu

def perguntar_sim_nao(pergunta: str) -> bool:
    """Pergunta s/n no terminal; qualquer coisa diferente de 's' vale como não."""
    resposta = input(f"{pergunta} (s/n): ").strip().lower()
    return resposta == "s"


def perguntar_numero(pergunta: str, padrao: float) -> float:
    """Lê um número do terminal; Enter vazio ou valor inválido usa o padrão."""
    resposta = input(f"{pergunta} [{padrao}]: ").strip()
    try:
        return float(resposta)
    except ValueError:
        return padrao


def menu_interativo() -> None:
    """Menu simples para quem roda o programa sem argumentos."""
    opcoes = {
        "1": "m1-enviar",
        "2": "m1-receber",
        "3": "m1-simular",
        "4": "m2-enviar",
        "5": "m2-receber",
        "6": "m2-simular",
    }
    while True:
        print("\n=== Camada Física usando Som ===")
        print("1) Método 1 - enviar (batidas)")
        print("2) Método 1 - receber (microfone)")
        print("3) Método 1 - simular sem microfone")
        print("4) Método 2 - enviar (MFSK)")
        print("5) Método 2 - receber (microfone)")
        print("6) Método 2 - simular sem microfone")
        print("0) Sair")
        escolha = input("Opção: ").strip()

        if escolha == "0":
            return
        if escolha not in opcoes:
            print("Opção inválida.")
            continue

        comando = opcoes[escolha]
        texto = ""
        guiado = False
        erro = False
        ruido = RUIDO_PADRAO
        duracao = DURACAO_RECEPCAO_M2

        if comando in COMANDOS_COM_TEXTO:
            texto = input("Texto: ")
            erro = perguntar_sim_nao("Simular erro de transmissão?")
        if comando == "m1-enviar":
            guiado = perguntar_sim_nao("Modo guiado (uma pessoa bate na mesa)?")
        if comando in ("m1-simular", "m2-simular"):
            ruido = perguntar_numero("Desvio padrão do ruído", RUIDO_PADRAO)
        if comando == "m2-receber":
            duracao = perguntar_numero("Segundos de gravação", DURACAO_RECEPCAO_M2)

        executar(comando, texto, guiado, erro, ruido, duracao)


def main(argumentos: list[str] | None = None) -> None:
    """Lê a linha de comando; sem subcomando, abre o menu interativo."""
    args = criar_parser().parse_args(argumentos)
    if args.comando is None:
        menu_interativo()
        return
    executar(args.comando,
             texto=getattr(args, "texto", ""),
             guiado=getattr(args, "guiado", False),
             erro=getattr(args, "erro", False),
             ruido=getattr(args, "ruido", RUIDO_PADRAO),
             duracao=getattr(args, "duracao", DURACAO_RECEPCAO_M2))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C, ou fim da entrada (Ctrl+Z / Ctrl+D) enquanto o menu espera
        print("\nEncerrado pelo usuário.")
