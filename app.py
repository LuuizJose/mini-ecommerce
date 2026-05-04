# Iteração 2 — branch iteracao2
"""
E-commerce — Flask + SQLite
Funcionalidades: cadastro/login, catálogo, carrinho, pedidos, painel do lojista
"""

import sqlite3
import os
import hashlib
import secrets
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g, jsonify
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DATABASE = os.path.join(os.path.dirname(__file__), 'instance', 'ecommerce.db')
os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

# ─── DB helpers ───────────────────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()

def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

# ─── Auth helpers ─────────────────────────────────────────────────────────────

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Faça login para continuar.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def lojista_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_tipo') != 'lojista':
            flash('Acesso restrito a lojistas.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ─── DB init ──────────────────────────────────────────────────────────────────

def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS usuario (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            nome     TEXT NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            senha    TEXT NOT NULL,
            tipo     TEXT NOT NULL DEFAULT 'cliente'  -- cliente | lojista
        );

        CREATE TABLE IF NOT EXISTS produto (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lojista_id  INTEGER NOT NULL REFERENCES usuario(id),
            nome        TEXT NOT NULL,
            descricao   TEXT,
            preco       REAL NOT NULL,
            estoque     INTEGER NOT NULL DEFAULT 0,
            categoria   TEXT,
            ativo       INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS pedido (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id  INTEGER NOT NULL REFERENCES usuario(id),
            total       REAL NOT NULL,
            status      TEXT NOT NULL DEFAULT 'aguardando_pagamento',
            criado_em   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            endereco    TEXT,
            pagamento   TEXT
        );

        CREATE TABLE IF NOT EXISTS item_pedido (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id   INTEGER NOT NULL REFERENCES pedido(id),
            produto_id  INTEGER NOT NULL REFERENCES produto(id),
            quantidade  INTEGER NOT NULL,
            preco_unit  REAL NOT NULL
        );
    """)
    db.commit()

    # Seed: lojista demo + produtos
    cur = db.execute("SELECT id FROM usuario WHERE email='loja@demo.com'")
    if not cur.fetchone():
        senha = hashlib.sha256(b'loja123').hexdigest()
        db.execute("INSERT INTO usuario (nome,email,senha,tipo) VALUES (?,?,?,?)",
                   ('Loja Demo', 'loja@demo.com', senha, 'lojista'))
        db.execute("INSERT INTO usuario (nome,email,senha,tipo) VALUES (?,?,?,?)",
                   ('Cliente Demo', 'cliente@demo.com',
                    hashlib.sha256(b'cliente123').hexdigest(), 'cliente'))
        db.commit()
        loj = db.execute("SELECT id FROM usuario WHERE email='loja@demo.com'").fetchone()[0]
        produtos = [
            (loj, 'Camiseta Básica', 'Algodão 100%, disponível em P/M/G', 49.90, 50, 'Roupas'),
            (loj, 'Tênis Casual', 'Solado antiderrapante, confortável', 189.90, 20, 'Calçados'),
            (loj, 'Mochila Urbana', '30 litros, compartimento para notebook', 159.90, 15, 'Acessórios'),
            (loj, 'Óculos de Sol', 'Proteção UV400, armação reforçada', 89.90, 30, 'Acessórios'),
            (loj, 'Calça Jeans', 'Corte slim, 5 bolsos', 129.90, 25, 'Roupas'),
            (loj, 'Boné Snapback', 'Aba reta, ajustável', 59.90, 40, 'Acessórios'),
        ]
        db.executemany(
            "INSERT INTO produto (lojista_id,nome,descricao,preco,estoque,categoria) VALUES (?,?,?,?,?,?)",
            produtos
        )
        db.commit()
    db.close()

# Inicializa o banco ao subir o servidor
with app.app_context():
    init_db()

# ─── Carrinho (sessão) ────────────────────────────────────────────────────────

def get_cart():
    return session.setdefault('cart', {})

def cart_count():
    return sum(get_cart().values())

app.jinja_env.globals['cart_count'] = cart_count

# ─── Rotas: Públicas ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    busca = request.args.get('q', '').strip()
    categoria = request.args.get('cat', '').strip()
    sql = "SELECT * FROM produto WHERE ativo=1"
    args = []
    if busca:
        sql += " AND nome LIKE ?"
        args.append(f'%{busca}%')
    if categoria:
        sql += " AND categoria=?"
        args.append(categoria)
    produtos = query(sql, args)
    categorias = query("SELECT DISTINCT categoria FROM produto WHERE ativo=1 ORDER BY categoria")
    return render_template('index.html', produtos=produtos, categorias=categorias,
                           busca=busca, categoria_sel=categoria)

@app.route('/produto/<int:pid>')
def produto(pid):
    p = query("SELECT * FROM produto WHERE id=? AND ativo=1", (pid,), one=True)
    if not p:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('index'))
    return render_template('produto.html', produto=p)

# ─── Rotas: Auth ──────────────────────────────────────────────────────────────

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome  = request.form['nome'].strip()
        email = request.form['email'].strip().lower()
        senha = request.form['senha']
        tipo  = request.form.get('tipo', 'cliente')
        if not nome or not email or not senha:
            flash('Preencha todos os campos.', 'danger')
        elif query("SELECT id FROM usuario WHERE email=?", (email,), one=True):
            flash('E-mail já cadastrado.', 'danger')
        else:
            uid = execute(
                "INSERT INTO usuario (nome,email,senha,tipo) VALUES (?,?,?,?)",
                (nome, email, hash_password(senha), tipo)
            )
            session['user_id']   = uid
            session['user_nome'] = nome
            session['user_tipo'] = tipo
            flash(f'Bem-vindo(a), {nome}!', 'success')
            return redirect(url_for('index'))
    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        senha = request.form['senha']
        u = query("SELECT * FROM usuario WHERE email=? AND senha=?",
                  (email, hash_password(senha)), one=True)
        if u:
            session['user_id']   = u['id']
            session['user_nome'] = u['nome']
            session['user_tipo'] = u['tipo']
            flash(f'Olá, {u["nome"]}!', 'success')
            return redirect(url_for('index'))
        flash('E-mail ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))

# ─── Rotas: Carrinho ─────────────────────────────────────────────────────────

@app.route('/carrinho')
def carrinho():
    cart = get_cart()
    itens = []
    total = 0
    for pid_str, qty in cart.items():
        p = query("SELECT * FROM produto WHERE id=?", (int(pid_str),), one=True)
        if p:
            subtotal = p['preco'] * qty
            itens.append({'produto': p, 'qty': qty, 'subtotal': subtotal})
            total += subtotal
    return render_template('carrinho.html', itens=itens, total=total)

@app.route('/carrinho/add/<int:pid>', methods=['POST'])
def add_cart(pid):
    qty = int(request.form.get('qty', 1))
    cart = get_cart()
    cart[str(pid)] = cart.get(str(pid), 0) + qty
    session.modified = True
    flash('Item adicionado ao carrinho!', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/carrinho/remove/<int:pid>')
def remove_cart(pid):
    cart = get_cart()
    cart.pop(str(pid), None)
    session.modified = True
    return redirect(url_for('carrinho'))

@app.route('/carrinho/update', methods=['POST'])
def update_cart():
    pid = str(request.form['pid'])
    qty = int(request.form['qty'])
    cart = get_cart()
    if qty <= 0:
        cart.pop(pid, None)
    else:
        cart[pid] = qty
    session.modified = True
    return redirect(url_for('carrinho'))

# ─── Rotas: Checkout / Pedidos ────────────────────────────────────────────────

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = get_cart()
    if not cart:
        flash('Seu carrinho está vazio.', 'warning')
        return redirect(url_for('carrinho'))

    if request.method == 'POST':
        endereco  = request.form['endereco'].strip()
        pagamento = request.form['pagamento']
        if not endereco:
            flash('Informe o endereço de entrega.', 'danger')
            return redirect(url_for('checkout'))

        # Calcular total e validar estoque
        total = 0
        itens = []
        for pid_str, qty in cart.items():
            p = query("SELECT * FROM produto WHERE id=? AND ativo=1", (int(pid_str),), one=True)
            if not p or p['estoque'] < qty:
                flash(f'Produto "{p["nome"] if p else pid_str}" indisponível.', 'danger')
                return redirect(url_for('carrinho'))
            total += p['preco'] * qty
            itens.append((p, qty))

        # Criar pedido
        pid = execute(
            "INSERT INTO pedido (cliente_id,total,status,endereco,pagamento) VALUES (?,?,?,?,?)",
            (session['user_id'], total, 'pagamento_confirmado', endereco, pagamento)
        )
        for p, qty in itens:
            execute(
                "INSERT INTO item_pedido (pedido_id,produto_id,quantidade,preco_unit) VALUES (?,?,?,?)",
                (pid, p['id'], qty, p['preco'])
            )
            execute("UPDATE produto SET estoque=estoque-? WHERE id=?", (qty, p['id']))

        session.pop('cart', None)
        flash('Pedido realizado com sucesso!', 'success')
        return redirect(url_for('pedido_detalhe', pid=pid))

    # GET — montar resumo
    itens, total = [], 0
    for pid_str, qty in cart.items():
        p = query("SELECT * FROM produto WHERE id=?", (int(pid_str),), one=True)
        if p:
            sub = p['preco'] * qty
            itens.append({'produto': p, 'qty': qty, 'subtotal': sub})
            total += sub
    return render_template('checkout.html', itens=itens, total=total)

@app.route('/pedidos')
@login_required
def pedidos():
    lista = query(
        "SELECT * FROM pedido WHERE cliente_id=? ORDER BY criado_em DESC",
        (session['user_id'],)
    )
    return render_template('pedidos.html', pedidos=lista)

@app.route('/pedidos/<int:pid>')
@login_required
def pedido_detalhe(pid):
    ped = query("SELECT * FROM pedido WHERE id=? AND cliente_id=?",
                (pid, session['user_id']), one=True)
    if not ped:
        flash('Pedido não encontrado.', 'danger')
        return redirect(url_for('pedidos'))
    itens = query(
        """SELECT ip.*, p.nome, p.categoria
           FROM item_pedido ip JOIN produto p ON p.id=ip.produto_id
           WHERE ip.pedido_id=?""", (pid,)
    )
    return render_template('pedido_detalhe.html', pedido=ped, itens=itens)

# ─── Rotas: Painel do Lojista ─────────────────────────────────────────────────

@app.route('/loja')
@login_required
@lojista_required
def loja_dashboard():
    produtos = query(
        "SELECT * FROM produto WHERE lojista_id=? ORDER BY id DESC",
        (session['user_id'],)
    )
    total_pedidos = query(
        """SELECT COUNT(DISTINCT p.id) as cnt FROM pedido p
           JOIN item_pedido ip ON ip.pedido_id=p.id
           JOIN produto pr ON pr.id=ip.produto_id
           WHERE pr.lojista_id=?""",
        (session['user_id'],), one=True
    )
    return render_template('loja_dashboard.html', produtos=produtos,
                           total_pedidos=total_pedidos['cnt'] if total_pedidos else 0)

@app.route('/loja/produto/novo', methods=['GET', 'POST'])
@login_required
@lojista_required
def loja_produto_novo():
    if request.method == 'POST':
        nome      = request.form['nome'].strip()
        descricao = request.form['descricao'].strip()
        preco     = float(request.form['preco'])
        estoque   = int(request.form['estoque'])
        categoria = request.form['categoria'].strip()
        if not nome or preco <= 0:
            flash('Preencha os campos obrigatórios.', 'danger')
        else:
            execute(
                "INSERT INTO produto (lojista_id,nome,descricao,preco,estoque,categoria) VALUES (?,?,?,?,?,?)",
                (session['user_id'], nome, descricao, preco, estoque, categoria)
            )
            flash('Produto cadastrado!', 'success')
            return redirect(url_for('loja_dashboard'))
    return render_template('loja_produto_form.html', produto=None)

@app.route('/loja/produto/<int:pid>/editar', methods=['GET', 'POST'])
@login_required
@lojista_required
def loja_produto_editar(pid):
    p = query("SELECT * FROM produto WHERE id=? AND lojista_id=?",
              (pid, session['user_id']), one=True)
    if not p:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('loja_dashboard'))
    if request.method == 'POST':
        execute(
            "UPDATE produto SET nome=?,descricao=?,preco=?,estoque=?,categoria=?,ativo=? WHERE id=?",
            (request.form['nome'], request.form['descricao'],
             float(request.form['preco']), int(request.form['estoque']),
             request.form['categoria'], int(request.form.get('ativo', 1)), pid)
        )
        flash('Produto atualizado!', 'success')
        return redirect(url_for('loja_dashboard'))
    return render_template('loja_produto_form.html', produto=p)

@app.route('/loja/pedidos')
@login_required
@lojista_required
def loja_pedidos():
    pedidos = query(
        """SELECT DISTINCT p.*, u.nome as cliente_nome
           FROM pedido p
           JOIN usuario u ON u.id=p.cliente_id
           JOIN item_pedido ip ON ip.pedido_id=p.id
           JOIN produto pr ON pr.id=ip.produto_id
           WHERE pr.lojista_id=?
           ORDER BY p.criado_em DESC""",
        (session['user_id'],)
    )
    return render_template('loja_pedidos.html', pedidos=pedidos)

@app.route('/loja/pedidos/<int:pid>/status', methods=['POST'])
@login_required
@lojista_required
def loja_atualizar_status(pid):
    novo_status = request.form['status']
    execute("UPDATE pedido SET status=? WHERE id=?", (novo_status, pid))
    flash('Status atualizado!', 'success')
    return redirect(url_for('loja_pedidos'))

# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True)