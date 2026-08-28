# 🤖 Tech Setup Bot — Shopee → Telegram

Bot de ofertas focado **100% em tecnologia e setup**.

Ele procura automaticamente produtos como:

- ⌨️ Teclados mecânicos
- 🖱️ Mouses e mousepads
- 🎧 Headsets e fones
- 🎙️ Microfones e webcams
- 🖥️ Monitores e suportes
- 💡 RGB, LEDs e iluminação
- 🪑 Mesas e cadeiras para setup
- 🔌 Hubs, cabos, carregadores e adaptadores
- 💻 Suportes para notebook e celular
- 🖥️ Componentes de PC
- 🎮 Controles e acessórios
- 📱 Eletrônicos em geral relacionados ao setup

## Como funciona

Se `SHOPEE_SEARCH_KEYWORD` ficar vazio, o bot alterna automaticamente entre várias buscas TECH a cada rodada.

Exemplo:

`teclado mecânico` → `mouse gamer` → `mousepad` → `monitor gamer` → `microfone USB` → ...

Assim o canal não fica preso a uma única categoria.

## 1. Instalação

```bash
pip install -r requirements.txt
```

## 2. Configure o `.env`

Preencha:

```env
SHOPEE_APP_ID=
SHOPEE_SECRET=
SHOPEE_AFFILIATE_ID=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL_ID=
TELEGRAM_CHANNEL_NAME=💻 Tech Setup
TELEGRAM_CHANNEL_LINK=

SUPABASE_URL=
SUPABASE_KEY=
```

Para usar somente uma categoria, coloque uma palavra em:

```env
SHOPEE_SEARCH_KEYWORD=teclado mecânico
```

Para voltar ao modo automático de TECH, deixe vazio.

## 3. Filtros

O padrão foi ajustado para o nicho TECH:

```env
SHOPEE_VENDAS_MINIMAS=100
SHOPEE_AVALIACAO_MINIMA=4.5
SHOPEE_BUSCA_BRUTA=50
SHOPEE_PRODUCT_LIMIT=1
```

O limite de 100 vendas ajuda a encontrar mais produtos de tecnologia do que o antigo limite de 1000.

## 4. Rodar

Uma rodada:

```bash
python main.py
```

Modo contínuo:

```bash
python main.py --loop
```

O bot posta no Telegram e registra os produtos no Supabase para evitar repetição.

## 5. Supabase

A tabela usada continua sendo:

```sql
create table public.produtos_postados (
    id bigint generated always as identity primary key,
    produto_id text unique not null,
    link text,
    criado_em timestamptz default now()
);
```

## 6. Segurança

O `.env` deste pacote foi deixado sem credenciais.

**Importante:** as credenciais que estavam no ZIP enviado anteriormente ficaram expostas no arquivo/conversa. Por segurança, gere novas credenciais na Shopee, Telegram e Supabase e coloque somente as novas no `.env`.

Nunca publique `.env` no GitHub.

## Estrutura

```text
ShopeeBot/
├── main.py
├── requirements.txt
├── .env
├── .gitignore
├── produtos_postados.json
└── README.md
```

## Render

Start Command:

```bash
python main.py --loop
```

Configure as variáveis do `.env` nas Environment Variables do Render.
