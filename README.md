# ShopFácil — Sistema de E-commerce
**Projeto Acadêmico · Prática Profissional em ADS · Mackenzie**

## Tecnologias
- **Back-end:** Python 3 + Flask
- **Banco de dados:** SQLite (via módulo `sqlite3` nativo)
- **Front-end:** HTML5 + CSS3 + JavaScript (sem frameworks externos)

## Pré-requisitos
- Python 3.9+
- Flask (`pip install flask`)

## Como rodar

```bash
# 1. Clone o repositório
git clone https://github.com/seu-grupo/shopfacil.git
cd shopfacil

# 2. (Opcional) Crie um ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install flask

# 4. Rode a aplicação
python app.py
```

Acesse: **http://localhost:5000**

## Contas demo (criadas automaticamente)

| Perfil   | E-mail               | Senha       |
|----------|----------------------|-------------|
| Cliente  | cliente@demo.com     | cliente123  |
| Lojista  | loja@demo.com        | loja123     |

## Estrutura do projeto

```
ecommerce/
├── app.py                  # Aplicação principal (rotas, lógica, banco)
├── instance/
│   └── ecommerce.db        # Banco SQLite (gerado automaticamente)
├── static/
│   ├── css/style.css       # Estilos
│   └── js/main.js          # Scripts
└── templates/
    ├── base.html           # Layout base (navbar, footer)
    ├── index.html          # Vitrine / catálogo
    ├── produto.html        # Detalhe do produto
    ├── login.html          # Login
    ├── cadastro.html       # Cadastro
    ├── carrinho.html       # Carrinho de compras
    ├── checkout.html       # Finalização do pedido
    ├── pedidos.html        # Lista de pedidos (cliente)
    ├── pedido_detalhe.html # Detalhe do pedido
    ├── loja_dashboard.html # Painel do lojista
    ├── loja_produto_form.html  # Form cadastro/edição de produto
    └── loja_pedidos.html   # Pedidos recebidos (lojista)
```

## Funcionalidades implementadas

### Cliente
- [x] Cadastro e login
- [x] Navegar/filtrar catálogo por categoria e busca
- [x] Ver detalhe do produto
- [x] Carrinho de compras (adicionar, remover, alterar quantidade)
- [x] Checkout com endereço e forma de pagamento
- [x] Histórico e detalhe de pedidos

### Lojista
- [x] Painel administrativo com estatísticas
- [x] Cadastrar, editar e ativar/desativar produtos
- [x] Visualizar pedidos recebidos
- [x] Atualizar status dos pedidos

## Banco de dados (esquema)

```sql
usuario       (id, nome, email, senha, tipo)
produto       (id, lojista_id, nome, descricao, preco, estoque, categoria, ativo)
pedido        (id, cliente_id, total, status, criado_em, endereco, pagamento)
item_pedido   (id, pedido_id, produto_id, quantidade, preco_unit)
```

## Próximos passos sugeridos
- Integrar gateway de pagamento real (Stripe / MercadoPago)
- Adicionar upload de imagens de produtos
- Implementar avaliações de produtos
- Adicionar cálculo de frete via API dos Correios
- Deploy em plataforma cloud (Railway, Render, Heroku)
