# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Método 2: transmissão por MFSK com 16 tons e detecção de erro por CRC-16.

Ideia geral
-----------
Cada símbolo é um tom puro escolhido entre 16 frequências possíveis. Como
16 = 2^4, cada símbolo carrega 4 bits (meio byte); um byte vira 2 símbolos.
O receptor mede a energia de cada uma das 16 frequências no trecho do
símbolo e escolhe a mais forte.

Para o eco da sala não atrapalhar, símbolos vizinhos usam conjuntos ("bancos")
diferentes de 16 frequências, em rodízio (ver BANCOS). O receptor sabe a
posição de cada símbolo e, portanto, qual banco medir.

O que vai pelo ar:
    [silêncio][preâmbulo (chirp)][pausa][símbolos do pacote][silêncio]

O preâmbulo é um "chirp" (tom que sobe de 1 kHz a 5 kHz). O receptor o
encontra por correlação cruzada e, a partir dele, sabe exatamente onde
começa cada símbolo.

Pacote:
    [comprimento: 1 byte][dados: 0 a 255 bytes][CRC-16: 2 bytes]
O CRC-16/CCITT é calculado sobre comprimento + dados. Se qualquer bit mudar
no caminho, o CRC recebido não confere e a mensagem é dada como FALHA.

Taxa teórica
------------
    bits por símbolo   = log2(16 tons)          = 4 bits
    duração do símbolo = 10 ms guarda + 20 ms   = 30 ms
    símbolos por seg.  = 1 / 0,030 s            ≈ 33,3 símbolos/s
    taxa teórica       = 4 bits x 33,3 símb./s  ≈ 133 bps

A taxa efetiva de uma mensagem é menor, porque o preâmbulo, os silêncios,
o byte de comprimento e o CRC também ocupam tempo. transmitir_texto imprime
os dois valores.
"""

import numpy as np

import audio
from config import TAXA_AMOSTRAGEM

# ---------------------------------------------------------------------------
# Constantes do Método 2
# ---------------------------------------------------------------------------

# Tons de dados
QUANTIDADE_TONS = 16      # 16 tons = 2^4, então cada símbolo carrega 4 bits
BITS_POR_SIMBOLO = 4
FREQUENCIA_BASE = 1000.0  # Hz, tom mais grave. Abaixo de ~500 Hz, alto-falantes de notebook
                          # e celular quase não tocam, e o ruído ambiente (ventilador,
                          # voz, trânsito) se concentra nos graves
ESPACAMENTO = 50.0        # Hz entre tons vizinhos = 1 / DURACAO_UTIL. Com esse espaçamento os
                          # tons são ortogonais: num trecho de 20 ms, a medida de um tom
                          # dá zero para todos os outros
BANCOS = 5                # Rodízio de bancos de tons: o símbolo na posição i usa o banco
                          # i % 5, cada banco com 16 tons próprios. Numa sala, o som de um
                          # símbolo continua ecoando (reverberação) por dezenas de ms; com o
                          # rodízio, um banco só volta a ser usado 5 símbolos (150 ms) depois,
                          # quando o eco já enfraqueceu. Em simulação de sala reverberante isso
                          # reduziu os erros de símbolo cerca de 10 vezes.
                          # Faixa total: 1000 Hz até 1000 + 5*16*50 - 50 = 4950 Hz, onde
                          # microfones e alto-falantes comuns respondem bem

# Tempo de cada símbolo
GUARDA = 0.010            # s. O tom já está tocando, mas o receptor ignora esse trecho:
                          # é onde chegam os ecos curtos (reflexos na mesa, nas paredes
                          # próximas) do símbolo anterior
DURACAO_UTIL = 0.020      # s. Trecho que o receptor analisa (resolução de 1/0,020 = 50 Hz)
DURACAO_SIMBOLO = GUARDA + DURACAO_UTIL  # 30 ms por símbolo
RAMPA = 0.002             # s. Volume sobe e desce suavemente no início e no fim de cada tom,
                          # porque um corte seco gera um "clique" com energia em todas as frequências
AMPLITUDE = 0.8           # pico do sinal (o máximo da placa de som é 1.0)

# Preâmbulo (sincronização)
PREAMBULO_FREQ_INICIAL = 1000.0  # Hz
PREAMBULO_FREQ_FINAL = 5000.0    # Hz. Um chirp largo dá um pico de correlação estreito,
                                 # o que permite saber o início com precisão de poucas amostras
DURACAO_PREAMBULO = 0.100        # s
PAUSA_APOS_PREAMBULO = 0.020     # s. Respiro entre o chirp e o 1º símbolo, para o eco
                                 # do chirp não cair em cima dele
LIMIAR_PREAMBULO = 0.3           # correlação normalizada mínima (0 a 1) para aceitar o
                                 # preâmbulo. Em ruído puro ela fica por volta de 0,1

# Pacote e áudio
SILENCIO_BORDAS = 0.2     # s de silêncio antes e depois. Algumas placas de som cortam o
                          # comecinho do áudio
TAMANHO_MAXIMO = 255      # bytes de dados (o comprimento ocupa 1 byte)


# ---------------------------------------------------------------------------
# Detecção de erro: CRC-16/CCITT
# ---------------------------------------------------------------------------

def crc16_ccitt(dados: bytes) -> int:
    """CRC-16/CCITT-FALSE (polinômio 0x1021, valor inicial 0xFFFF), bit a bit.

    É o resto da divisão binária da mensagem pelo polinômio. Feito bit a bit
    para ficar fácil de acompanhar. Exemplo: crc16_ccitt(b"123456789") == 0x29B1
    """
    crc = 0xFFFF
    for byte in dados:
        crc = crc ^ (byte << 8)  # coloca o byte nos 8 bits mais altos do registrador
        for _ in range(8):
            if crc & 0x8000:     # bit mais alto é 1: "cabe" o polinômio, então subtrai (XOR)
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def montar_pacote(dados: bytes) -> bytes:
    """Monta [comprimento][dados][CRC-16 em 2 bytes, byte mais alto primeiro]."""
    if len(dados) > TAMANHO_MAXIMO:
        raise ValueError(f"mensagem com {len(dados)} bytes; o máximo é {TAMANHO_MAXIMO}")
    cabecalho_e_dados = bytes([len(dados)]) + dados
    crc = crc16_ccitt(cabecalho_e_dados)
    return cabecalho_e_dados + bytes([crc >> 8, crc & 0xFF])


# ---------------------------------------------------------------------------
# Bytes <-> símbolos
# ---------------------------------------------------------------------------

def bytes_para_simbolos(dados: bytes) -> list[int]:
    """Cada byte vira 2 símbolos de 4 bits (0 a 15): primeiro a metade alta."""
    simbolos = []
    for byte in dados:
        simbolos.append(byte >> 4)    # 4 bits mais altos
        simbolos.append(byte & 0x0F)  # 4 bits mais baixos
    return simbolos


def simbolos_para_bytes(simbolos: list[int]) -> bytes:
    """Caminho inverso: junta os símbolos de 2 em 2 para formar bytes."""
    resultado = bytearray()
    for i in range(0, len(simbolos) - 1, 2):
        resultado.append((simbolos[i] << 4) | simbolos[i + 1])
    return bytes(resultado)


def frequencia_do_simbolo(simbolo: int, posicao: int) -> float:
    """Frequência do `simbolo` (0 a 15) quando ele é o símbolo número `posicao` do pacote.

    Banco 0: 1000, 1050, ..., 1750 Hz; banco 1: 1800 a 2550 Hz; ... banco 4: 4200 a 4950 Hz.
    """
    banco = posicao % BANCOS
    return FREQUENCIA_BASE + (banco * QUANTIDADE_TONS + simbolo) * ESPACAMENTO


# ---------------------------------------------------------------------------
# Emissor
# ---------------------------------------------------------------------------

def amostras(duracao: float, taxa: int) -> int:
    """Converte uma duração em segundos para número de amostras."""
    return int(round(duracao * taxa))


def aplicar_rampas(sinal: np.ndarray, taxa: int) -> np.ndarray:
    """Suaviza início e fim do sinal (meia senoide de RAMPA segundos) para evitar cliques."""
    n = amostras(RAMPA, taxa)
    rampa = 0.5 - 0.5 * np.cos(np.pi * np.arange(n) / n)  # sobe de 0 até quase 1
    suavizado = sinal.copy()
    suavizado[:n] *= rampa
    suavizado[-n:] *= rampa[::-1]
    return suavizado


def gerar_tom(frequencia: float, duracao: float, taxa: int) -> np.ndarray:
    """Senoide pura de `frequencia` Hz, com rampas nas pontas."""
    t = np.arange(amostras(duracao, taxa)) / taxa
    return aplicar_rampas(AMPLITUDE * np.sin(2 * np.pi * frequencia * t), taxa)


def gerar_preambulo(taxa: int = TAXA_AMOSTRAGEM) -> np.ndarray:
    """Chirp linear: frequência sobe de PREAMBULO_FREQ_INICIAL a PREAMBULO_FREQ_FINAL.

    A fase é a integral da frequência: f(t) = f0 + k*t  =>  fase = 2*pi*(f0*t + k*t²/2).
    """
    t = np.arange(amostras(DURACAO_PREAMBULO, taxa)) / taxa
    k = (PREAMBULO_FREQ_FINAL - PREAMBULO_FREQ_INICIAL) / DURACAO_PREAMBULO
    fase = 2 * np.pi * (PREAMBULO_FREQ_INICIAL * t + k * t ** 2 / 2)
    return aplicar_rampas(AMPLITUDE * np.sin(fase), taxa)


def modular(dados: bytes, simular_erro: bool = False) -> np.ndarray:
    """Transforma os dados em áudio: silêncio + preâmbulo + pausa + tons + silêncio.

    Com simular_erro=True, 1 bit do pacote é invertido DEPOIS de calcular o CRC
    (o bit mais baixo do byte logo após o comprimento, que é o 1º byte de dados).
    Assim o receptor detecta a falha, como aconteceria com um erro no ar.
    Numa mensagem vazia esse byte já é o CRC; o receptor também acusa a falha.
    """
    taxa = TAXA_AMOSTRAGEM
    pacote = bytearray(montar_pacote(dados))
    if simular_erro:
        pacote[1] = pacote[1] ^ 0b00000001

    silencio = np.zeros(amostras(SILENCIO_BORDAS, taxa))
    pausa = np.zeros(amostras(PAUSA_APOS_PREAMBULO, taxa))
    partes = [silencio, gerar_preambulo(taxa), pausa]
    simbolos = bytes_para_simbolos(bytes(pacote))
    for posicao in range(len(simbolos)):
        frequencia = frequencia_do_simbolo(simbolos[posicao], posicao)
        partes.append(gerar_tom(frequencia, DURACAO_SIMBOLO, taxa))
    partes.append(silencio)
    return np.concatenate(partes).astype(np.float32)


# ---------------------------------------------------------------------------
# Receptor
# ---------------------------------------------------------------------------

def correlacao_normalizada(sinal: np.ndarray, modelo: np.ndarray) -> np.ndarray:
    """Para cada posição k, o quanto sinal[k : k+len(modelo)] se parece com o modelo (0 a 1).

    Fórmula, com trecho = sinal[k : k+len(modelo)]:
        soma(trecho * modelo) / raiz(soma(trecho²) * soma(modelo²))
    Ou seja, a correlação cruzada dividida pela energia dos dois trechos, então
    o resultado não depende do volume da gravação. A correlação é feita pela FFT
    (multiplicar espectros equivale a correlacionar no tempo), que é muito mais
    rápida que np.correlate numa gravação de vários segundos.
    """
    m = len(modelo)
    posicoes = len(sinal) - m + 1

    # Tamanho da FFT: potência de 2 com espaço para não "dar a volta" no fim do vetor
    tamanho_fft = 1
    while tamanho_fft < len(sinal) + m:
        tamanho_fft *= 2
    espectro = np.fft.rfft(sinal, tamanho_fft) * np.conj(np.fft.rfft(modelo, tamanho_fft))
    correlacao = np.fft.irfft(espectro, tamanho_fft)[:posicoes]

    # Energia do sinal em cada janela de m amostras, usando soma acumulada:
    # soma(sinal[k:k+m]²) = acumulada[k+m] - acumulada[k]
    acumulada = np.concatenate(([0.0], np.cumsum(sinal ** 2)))
    energia_janelas = acumulada[m:] - acumulada[:-m]
    energia_modelo = np.sum(modelo ** 2)
    # Piso de energia: em silêncio absoluto a energia dá zero (ou um resíduo de
    # arredondamento), e dividir por ela criaria um "pico" falso
    energia_janelas = np.maximum(energia_janelas, 1e-6 * energia_modelo)

    # abs(): alguns microfones invertem a polaridade, e o pico fica negativo
    return np.abs(correlacao) / np.sqrt(energia_janelas * energia_modelo)


def encontrar_inicio_dos_dados(sinal: np.ndarray, taxa: int) -> int | None:
    """Acha o preâmbulo e devolve o índice onde começa o 1º símbolo (None se não achar)."""
    modelo = gerar_preambulo(taxa)
    if len(sinal) < len(modelo):
        return None
    correlacao = correlacao_normalizada(sinal, modelo)
    pico = int(np.argmax(correlacao))
    if correlacao[pico] < LIMIAR_PREAMBULO:
        return None
    return pico + len(modelo) + amostras(PAUSA_APOS_PREAMBULO, taxa)


def energias_dos_tons(trecho: np.ndarray, posicao: int, taxa: int) -> np.ndarray:
    """Energia de cada um dos 16 tons do banco usado na `posicao` do pacote.

    Para cada frequência, multiplica o trecho por uma senoide complexa daquela
    frequência e soma. É a DFT calculada só nos 16 pontos que interessam.
    """
    t = np.arange(len(trecho)) / taxa
    energias = np.zeros(QUANTIDADE_TONS)
    for simbolo in range(QUANTIDADE_TONS):
        frequencia = frequencia_do_simbolo(simbolo, posicao)
        componente = np.sum(trecho * np.exp(-2j * np.pi * frequencia * t))
        energias[simbolo] = np.abs(componente) ** 2
    return energias


def detectar_simbolos(sinal: np.ndarray, inicio: int, quantidade: int,
                      taxa: int) -> list[int] | None:
    """Lê `quantidade` símbolos a partir de `inicio`. None se o sinal acabar antes."""
    n_simbolo = amostras(DURACAO_SIMBOLO, taxa)
    n_guarda = amostras(GUARDA, taxa)
    n_util = amostras(DURACAO_UTIL, taxa)

    simbolos = []
    for posicao in range(quantidade):
        comeco = inicio + posicao * n_simbolo + n_guarda  # pula a guarda, onde chega o eco
        trecho = sinal[comeco:comeco + n_util]
        if len(trecho) < n_util:
            return None
        energias = energias_dos_tons(trecho, posicao, taxa)
        simbolos.append(int(np.argmax(energias)))
    return simbolos


def demodular(sinal: np.ndarray, taxa: int = TAXA_AMOSTRAGEM) -> tuple[bytes | None, bool]:
    """Recupera os dados de um áudio. Devolve (dados, crc_ok).

    (None, False) se não achar o preâmbulo ou se o áudio acabar antes do fim do pacote.
    Se o CRC não conferir, devolve os dados como chegaram (corrompidos) e False.
    """
    sinal = np.asarray(sinal, dtype=np.float64)
    if sinal.ndim > 1:  # gravação no formato (amostras, canais): usa só o 1º canal
        sinal = sinal[:, 0]
    inicio = encontrar_inicio_dos_dados(sinal, taxa)
    if inicio is None:
        return None, False

    # Os 2 primeiros símbolos formam o byte de comprimento
    simbolos_comprimento = detectar_simbolos(sinal, inicio, 2, taxa)
    if simbolos_comprimento is None:
        return None, False
    comprimento = simbolos_para_bytes(simbolos_comprimento)[0]

    # Pacote inteiro: comprimento (1) + dados + CRC (2), com 2 símbolos por byte
    total_simbolos = 2 * (1 + comprimento + 2)
    simbolos = detectar_simbolos(sinal, inicio, total_simbolos, taxa)
    if simbolos is None:
        return None, False
    pacote = simbolos_para_bytes(simbolos)

    dados = pacote[1:1 + comprimento]
    crc_recebido = (pacote[-2] << 8) | pacote[-1]
    crc_ok = crc16_ccitt(pacote[:-2]) == crc_recebido
    return dados, crc_ok


def taxa_teorica_bps() -> float:
    """Bits por símbolo / duração do símbolo = 4 / 0,030 ≈ 133 bps."""
    return BITS_POR_SIMBOLO / DURACAO_SIMBOLO


def relatar_mensagem(dados: bytes | None, crc_ok: bool) -> str:
    """Linha para o terminal dizendo se a mensagem chegou íntegra ou não."""
    if dados is None:
        return "[FALHA DE TRANSMISSÃO] preâmbulo não encontrado ou mensagem incompleta"
    texto = dados.decode("utf-8", errors="replace")
    if not crc_ok:
        return f"[FALHA DE TRANSMISSÃO] CRC não confere; chegou corrompido: {texto!r}"
    return f"[SUCESSO] {texto!r} (CRC-16 confere)"


# ---------------------------------------------------------------------------
# Uso pelo terminal (alto-falante e microfone)
# ---------------------------------------------------------------------------

def transmitir_texto(texto: str, simular_erro: bool = False) -> None:
    """Codifica o texto em UTF-8, modula e toca no alto-falante."""
    dados = texto.encode("utf-8")
    sinal = modular(dados, simular_erro)
    duracao = len(sinal) / TAXA_AMOSTRAGEM

    print(f"Método 2 (MFSK 16 tons + CRC-16): {len(dados)} bytes de dados "
          f"({len(dados) + 3} com comprimento e CRC)")
    print(f"Taxa teórica: {taxa_teorica_bps():.1f} bps | duração do áudio: {duracao:.2f} s | "
          f"taxa efetiva com preâmbulo e silêncios: {8 * len(dados) / duracao:.1f} bps")
    if simular_erro:
        print("[SIMULAÇÃO DE ERRO] 1 bit dos dados foi invertido DEPOIS de calcular o CRC.")
    print("Tocando...")
    audio.tocar(sinal, TAXA_AMOSTRAGEM)
    print("Transmissão concluída.")


def receber(duracao: float = 10.0) -> None:
    """Grava `duracao` segundos do microfone, demodula e mostra SUCESSO ou FALHA."""
    print(f"Gravando por {duracao:.1f} s. Comece a transmissão no outro computador.")
    sinal = audio.gravar(duracao, TAXA_AMOSTRAGEM)
    print("Gravação concluída. Decodificando...")
    dados, crc_ok = demodular(sinal, TAXA_AMOSTRAGEM)
    print(relatar_mensagem(dados, crc_ok))
    if dados is None:
        print("Dica: aumente o volume e confira se a gravação dura o bastante "
              "(cerca de 0,7 s + 60 ms por byte de mensagem).")
