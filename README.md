# Projeto Barra-Bola

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gusnavasco/projeto-barra-bola/blob/main/analise_dados_frequencia/gerar_bode_e_visualizar_senoides.ipynb)

Este repositório contém os códigos e a documentação utilizados no PFC (de Engenharia de Controle e Automação) dos autores, baseado num sistema **Barra-Bola**. 

O objetivo principal deste projeto é servir como **plataforma didática** para estudantes que desejam visualizar, na prática, conceitos de teoria de controle aprendidos no curso.

## Estrutura do Repositório

* `/analise_dados`: Scripts em Python para visualização de dados e geração do Diagrama de Bode.
* `/apendices`: Materiais complementares referenciados na monografia do PFC.
* `/dados_exemplo`: Arquivo `.csv` de exemplo, com dados reais coletados do sistema.
* `/docs`: Diagrama de conexões do hardware, foto do projeto e diagrama do fluxo de dados do sistema.
* `/firmware`: Contém o código do ESP32.


## Como usar este projeto

### 1. Execução dos experimentos - ESP32 e SCADA

O diagrama de conexões do hardware, na pasta docs, explica como conectar as peças do hardware.

Será necessário compilar o firmware no ESP32 (caso não já esteja compilado), o que pode ser feito através do programa Arduino IDE.
Certifique-se de instalar as seguintes bibliotecas antes de compilar:
- `ESP32Servo`
- `Adafruit_VL53L0X`
- `modbus-esp8266`

Por fim, deve ser utilizada a [plataforma SCADA](https://drive.google.com/drive/folders/1yL5zZIkXXlfEQxrBfF8c0DKOGJqZQ0hC?usp=drive_link) desenvolvida no PFC para visualização gráfica das variáveis do sistema. Lá também será possível alterar os ganhos dos controladores desenvolvidos dinamicamente, realizar ensaios em frequência, salvar e exportar dados dos experimentos e até ler sobre a teoria dos controladores utilizados (PID e avanço de fase) e da própria ferramenta SCADA (de forma genérica).

### 2. Análise de Dados e Diagrama de Bode (para dados de ensaios em frequência)

Para rodar os códigos de análise de dados, clique no botão "Open in Colab" no topo desta página. O Google Colab abrirá o notebook interativo (`gerar_bode_e_visualizar_senoides.ipynb`), em que você pode fazer o upload de um arquivo `.csv` gerado pela [plataforma SCADA](https://drive.google.com/drive/folders/1yL5zZIkXXlfEQxrBfF8c0DKOGJqZQ0hC?usp=drive_link), gerando os gráficos sem instalar nada no computador.

Também foram deixados os arquivos `.py` na pasta "analise_dados_frequencia", caso prefera rodar localmente. Recomenda-se a utilização de um ambiente virtual, em que devem ser instaladas as dependências: `pip install pandas numpy matplotlib`
