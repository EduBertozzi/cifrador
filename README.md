# Cifrador

Sobe uma música (arquivo ou link) e recebe a **cifra pro violão**, sincronizada com o áudio, com o **capotraste que deixa tudo em acorde aberto**.

Roda **100% no seu computador**. Nada vai pra nuvem.

## Como abrir

**Mac**

```bash
brew install ffmpeg
cd cifrador
chmod +x iniciar.sh
./iniciar.sh
```

**Windows (PC com a GTX 1060)**

```bat
winget install Gyan.FFmpeg
```

Fecha e abre o terminal, depois dá dois cliques no `iniciar.bat`.

Na primeira vez ele instala tudo sozinho (uns 5 a 10 minutos, baixa uns 3 GB). Depois abre direto no navegador em `http://127.0.0.1:8765`.

Também dá pra usar pelo terminal:

```bash
.venv/bin/python -m cifrador musica.mp3
.venv/bin/python -m cifrador "https://youtu.be/..." --qualidade maximo
```

## Por que ele é preciso

| Etapa | O que faz | Por que ajuda |
|---|---|---|
| **Separação (Demucs)** | Divide em bateria, baixo, voz e resto | Os modelos ouvem só a harmonia, sem a voz e a bateria atrapalhando |
| **Correção de afinação** | Mede quantos cents a gravação está fora do 440 Hz e corrige | Música gravada meio tom "torto" confunde qualquer modelo |
| **2 modelos de acorde** | lv-chordia (ensemble de 5 redes, ISMIR 2019) e BTC (transformer, ISMIR 2019), 170 tipos de acorde | Cada um erra em lugares diferentes |
| **4 opiniões por trecho** | Cada modelo ouve a mixagem inteira e o stem harmônico | Mais votos, menos erro |
| **Votação por batida** | A música vira uma grade de meia batida e cada opinião vota | Acorde troca no ritmo, não no meio do nada |
| **Votos parciais** | Quem ouviu C7M dá meio voto pro C | Extensão (7M, 9, inversão) só aparece quando os modelos concordam |
| **Viterbi com compasso** | Escolhe a sequência mais provável, trocar no tempo forte é barato e no contratempo é caro | Some aquele acorde "piscando" de meio segundo |
| **Tom da música** | Campo harmônico dá um empurrãozinho nos empates | Desempata C x Am, por exemplo |

Trechos com **confiança baixa** aparecem sublinhados pontilhado na cifra e listrados na linha do tempo. Vale conferir de ouvido.

## Como ele escolhe o capo

Pra cada casa de 0 a 9 ele desce os acordes e procura a forma mais fácil de cada um numa biblioteca de formas (abertas, pestana na 6ª, pestana na 5ª, forma de Ré). Cada forma ganha uma nota:

| Conta a favor | Conta contra |
|---|---|
| Cordas soltas soando (é isso que deixa "lindo") | Pestana |
| Acorde cheio, 5 ou 6 cordas | Abertura grande entre os dedos |
| Poucos dedos | Casa muito alta |
| | Capo acima da 5ª casa (som fino) |

A nota final pesa pelo tempo que cada acorde toca na música. Um acorde chato que aparece 2 segundos quase não pesa. Na tela você vê o recomendado (★) e pode clicar em qualquer outro.

## Na tela

| Controle | O que faz |
|---|---|
| **Capotraste** | Troca a casa e a cifra inteira já mostra as formas |
| **Tom − / +** | Transpõe meio tom por vez e recalcula o melhor capo |
| **Simplificar** | Vira tudo maior, menor e 7 (bom pra tocar de primeira) |
| **Mostrar acorde real** | Mostra o acorde que soa em vez da forma da mão |
| **Com letra / Compassos** | Cifra com a letra (Whisper) ou grade de compassos |
| **Clicar num acorde** | Pula o áudio pra ali |
| **Espaço** | Play e pause |
| **Baixar .txt** | Exporta a cifra como está na tela |

## Rápido x Máxima precisão

| Modo | Separação | Tempo (música de 3 min) |
|---|---|---|
| Rápido | htdemucs | ~1 min na GTX 1060, ~2 a 3 min no Mac |
| Máxima precisão | htdemucs_ft (4 modelos) + 2 passadas | ~3 min na GTX 1060, ~8 a 10 min no Mac |

## Arquivos

```
cifrador/
  theory.py       acordes, nomes (padrão BR: 7M, m7(b5), °), tonalidade
  shapes.py       biblioteca de formas e otimizador de capo
  audio.py        download por link, conversão, correção de afinação
  separation.py   Demucs
  recognizers.py  lv-chordia e BTC
  rhythm.py       batidas, compasso
  fusion.py       votação e Viterbi
  lyrics.py       letra com tempo de cada palavra
  pipeline.py     junta tudo
  server.py       API local
  static/         interface
musicas/          cada análise fica salva aqui (abre de novo sem reprocessar)
```

## Limites honestos

- Nenhum modelo acerta 100%. Os dois juntos acertam por volta de **8 em cada 10** acordes em pop e rock gravado, e erram mais em jazz, música só voz e violão muito dedilhado.
- **Inversão** (C/E) e **extensões** (9, 11, 13) são as partes mais difíceis. Na dúvida ele prefere o acorde mais simples.
- Música que muda de compasso no meio pode desalinhar a grade de compassos (a cifra com letra não depende disso).
- O modelo BTC é baixado do Hugging Face na primeira vez. Se não baixar, o Cifrador segue só com o lv-chordia e avisa.
- O Whisper pode errar palavras da letra. Os acordes não dependem dela.
