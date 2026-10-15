import os, sqlite3, json, secrets, re, io, calendar
from datetime import datetime, timedelta, date
from functools import wraps
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, request, redirect, url_for, render_template, session, flash, abort, send_file, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.environ.get('APP_DB',os.path.join(BASE,'estofados.db'))
UPLOAD_DIR=os.environ.get('UPLOAD_DIR',os.path.join(BASE,'uploads'))
app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config.update(MAX_CONTENT_LENGTH=8*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('HTTPS','0')=='1', SESSION_REFRESH_EACH_REQUEST=True, PERMANENT_SESSION_LIFETIME=timedelta(days=7))
STATUSES=['Novo','Estimativa enviada','Visita agendada','Orçamento final','Aprovado','Coleta agendada','Em produção','Pronto para entrega','Entregue','Perdido','Cancelado']
PAY=['Pix','Cartão','Dinheiro','Transferência']

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB)), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY,name TEXT NOT NULL,whatsapp TEXT DEFAULT '',margin REAL DEFAULT 40,pix_discount REAL DEFAULT 5,card_fee REAL DEFAULT 0,card_installments INTEGER DEFAULT 10,weekly_capacity INTEGER DEFAULT 5,workdays TEXT DEFAULT '0,1,2,3,4',commission_rate REAL DEFAULT 20,lead_days INTEGER DEFAULT 3);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','owner','staff')),company_id INTEGER,active INTEGER DEFAULT 1,FOREIGN KEY(company_id) REFERENCES companies(id));
        CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL,name TEXT NOT NULL,phone TEXT DEFAULT '',cpf TEXT DEFAULT '',address TEXT DEFAULT '',origin TEXT DEFAULT '',notes TEXT DEFAULT '',created TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(company_id) REFERENCES companies(id));
        CREATE TABLE IF NOT EXISTS catalog(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL,category TEXT NOT NULL,name TEXT NOT NULL,unit TEXT DEFAULT 'un',cost REAL NOT NULL DEFAULT 0,markup REAL DEFAULT 0,active INTEGER DEFAULT 1,FOREIGN KEY(company_id) REFERENCES companies(id));
        CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL,client_id INTEGER NOT NULL,description TEXT NOT NULL,dimensions TEXT DEFAULT '',status TEXT DEFAULT 'Novo',items_json TEXT DEFAULT '[]',other_cost REAL DEFAULT 0,freight_cost REAL DEFAULT 0,labor_cost REAL DEFAULT 0,total_cost REAL DEFAULT 0,price REAL DEFAULT 0,pix_price REAL DEFAULT 0,card_price REAL DEFAULT 0,payment_method TEXT DEFAULT 'Pix',paid REAL DEFAULT 0,actual_cost REAL,estimated_delivery TEXT,actual_delivery TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP,notes TEXT DEFAULT '',FOREIGN KEY(company_id) REFERENCES companies(id),FOREIGN KEY(client_id) REFERENCES clients(id));
        CREATE TABLE IF NOT EXISTS visits(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL,client_id INTEGER NOT NULL,quote_id INTEGER,starts_at TEXT NOT NULL,minutes INTEGER DEFAULT 60,status TEXT DEFAULT 'Agendada',notes TEXT DEFAULT '',FOREIGN KEY(company_id) REFERENCES companies(id),FOREIGN KEY(client_id) REFERENCES clients(id));
        CREATE TABLE IF NOT EXISTS costs(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL,quote_id INTEGER,description TEXT NOT NULL,amount REAL NOT NULL,date TEXT NOT NULL,FOREIGN KEY(company_id) REFERENCES companies(id));
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL,quote_id INTEGER NOT NULL,kind TEXT NOT NULL,filepath TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(company_id) REFERENCES companies(id),FOREIGN KEY(quote_id) REFERENCES quotes(id));
        CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY,company_id INTEGER,actor TEXT,detail TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        if not c.execute('SELECT 1 FROM companies').fetchone():
            c.execute("INSERT INTO companies(name) VALUES ('Abreu Estofados'),('Luiz Estofados')")
        if not c.execute('SELECT 1 FROM users').fetchone():
            password=os.environ.get('ADMIN_PASSWORD','Trocar@12345')
            c.execute('INSERT INTO users(email,password,role,company_id) VALUES (?,?,?,NULL)',('admin@estofados.local',generate_password_hash(password),'admin'))
        c.commit()

@app.before_request
def csrf_guard():
    if 'csrf' not in session: session['csrf']=secrets.token_hex(24)
    if request.method=='POST' and request.form.get('csrf')!=session.get('csrf'): abort(400,'Token inválido. Atualize a página.')

@app.context_processor
def ctx():
    return dict(csrf=session.get('csrf'),me=session.get('user'),statuses=STATUSES,money=money,today=date.today().isoformat())

def money(value):
    return 'R$ '+f'{float(value or 0):,.2f}'.replace(',','X').replace('.',',').replace('X','.')

def num(value,default=0):
    try: return max(0,float(str(value or '').replace(',','.')))
    except: return default

def ri(x): return int(round(x*100))/100

def login_required(fn):
    @wraps(fn)
    def wrapper(*args,**kwargs):
        if not session.get('user'): return redirect(url_for('login'))
        return fn(*args,**kwargs)
    return wrapper

def allowed_company(cid):
    u=session.get('user')
    if not u: abort(401)
    if u['role']!='admin' and u['company_id']!=cid: abort(403)

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a,**kw):
            if not session.get('user'): return redirect(url_for('login'))
            if session['user']['role'] not in roles: abort(403)
            return fn(*a,**kw)
        return wrapper
    return decorator

def current_company():
    u=session['user']
    if u['role']=='admin':
        requested=request.values.get('company_id',type=int)
        if requested is not None:
            if requested not in (1,2): abort(404)
            session['active_company_id']=requested
        cid=session.get('active_company_id',1)
        if cid not in (1,2): cid=1
    else:
        cid=u['company_id']
    allowed_company(cid)
    with conn() as c:
        company=c.execute('SELECT * FROM companies WHERE id=?',(cid,)).fetchone()
        if not company: abort(404)
        return dict(company)

def row_owned(table,id,cid):
    if table not in ['clients','catalog','quotes','visits','costs','documents']: abort(400)
    with conn() as c: r=c.execute(f'SELECT * FROM {table} WHERE id=? AND company_id=?',(id,cid)).fetchone()
    if r is None: abort(404)
    return dict(r)

def audit(cid,detail):
    with conn() as c: c.execute('INSERT INTO logs(company_id,actor,detail) VALUES(?,?,?)',(cid,session['user']['email'],detail))

def next_delivery(cid, capacity):
    capacity=max(1,int(capacity))
    today=date.today()
    with conn() as c:
        rows=c.execute("SELECT estimated_delivery FROM quotes WHERE company_id=? AND status NOT IN ('Entregue','Perdido','Cancelado') AND estimated_delivery IS NOT NULL",(cid,)).fetchall()
    counts={}
    for r in rows:
        if r['estimated_delivery']: counts[r['estimated_delivery']]=counts.get(r['estimated_delivery'],0)+1
    for offset in range(3,365):
        d=today+timedelta(days=offset)
        if d.weekday()>=5: continue
        begin=d-timedelta(days=d.weekday()); week=[(begin+timedelta(days=j)).isoformat() for j in range(7)]
        if sum(counts.get(k,0) for k in week)<capacity: return d.isoformat()
    return (today+timedelta(days=365)).isoformat()

@app.route('/login',methods=['GET','POST'])
def login():
    if session.get('user') and request.method=='GET': return redirect(url_for('dashboard'))
    if request.method=='POST':
        with conn() as c: u=c.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND active=1',(request.form.get('email',''),)).fetchone()
        if u and check_password_hash(u['password'],request.form.get('password','')):
            session.clear();session.permanent=True;session['csrf']=secrets.token_hex(24);session['user']=dict(id=u['id'],email=u['email'],role=u['role'],company_id=u['company_id']);session['active_company_id']=u['company_id'] or 1;return redirect(url_for('dashboard'))
        flash('E-mail ou senha inválidos.','error')
    return render_template('login.html')

@app.route('/logout',methods=['POST'])
@login_required
def logout():session.clear();return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    comp=current_company();cid=comp['id']
    with conn() as c:
        jobs=c.execute('SELECT q.*,cl.name client_name FROM quotes q JOIN clients cl ON cl.id=q.client_id WHERE q.company_id=? ORDER BY q.id DESC',(cid,)).fetchall()
        visits=c.execute('SELECT v.*,cl.name client_name FROM visits v JOIN clients cl ON cl.id=v.client_id WHERE v.company_id=? ORDER BY starts_at DESC LIMIT 5',(cid,)).fetchall()
        clients=c.execute('SELECT COUNT(*) n FROM clients WHERE company_id=?',(cid,)).fetchone()['n']
        direct=c.execute('SELECT SUM(amount) n FROM costs WHERE company_id=? AND quote_id IS NULL',(cid,)).fetchone()['n'] or 0
    completed=[j for j in jobs if j['status']=='Entregue']
    revenue=sum(j['price'] for j in completed)
    base_cost=sum((j['actual_cost'] if j['actual_cost'] is not None else j['total_cost']) for j in completed)+direct
    profit=revenue-base_cost
    metrics=dict(clients=clients,quotes=len(jobs),active=len([j for j in jobs if j['status'] not in ('Entregue','Perdido','Cancelado')]),revenue=revenue,cost=base_cost,profit=profit,commission=max(0,profit)*comp['commission_rate']/100)
    return render_template('dashboard.html',comp=comp,metrics=metrics,jobs=jobs[:12],visits=visits)

@app.route('/clients',methods=['GET','POST'])
@login_required
def clients():
    comp=current_company(); cid=comp['id']
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if not name:flash('Informe o nome.','error')
        else:
            with conn() as c: c.execute('INSERT INTO clients(company_id,name,phone,cpf,address,origin,notes) VALUES(?,?,?,?,?,?,?)',(cid,name,request.form.get('phone',''),request.form.get('cpf',''),request.form.get('address',''),request.form.get('origin',''),request.form.get('notes','')))
            audit(cid,'Cliente cadastrado: '+name);flash('Cliente cadastrado.');return redirect(url_for('clients',company_id=cid))
    with conn() as c: rows=c.execute('SELECT * FROM clients WHERE company_id=? ORDER BY id DESC',(cid,)).fetchall()
    return render_template('clients.html',comp=comp,rows=rows)

@app.route('/catalog',methods=['GET','POST'])
@login_required
def catalog():
    comp=current_company();cid=comp['id']
    if request.method=='POST':
        if request.form.get('operation')=='delete':
            r=row_owned('catalog',int(request.form['id']),cid)
            with conn() as c:c.execute('UPDATE catalog SET active=0 WHERE id=? AND company_id=?',(r['id'],cid))
        else:
            with conn() as c:c.execute('INSERT INTO catalog(company_id,category,name,unit,cost,markup) VALUES(?,?,?,?,?,?)',(cid,request.form['category'],request.form['name'],request.form.get('unit','un'),num(request.form.get('cost')),num(request.form.get('markup'))))
        return redirect(url_for('catalog',company_id=cid))
    with conn() as c:rows=c.execute('SELECT * FROM catalog WHERE company_id=? AND active=1 ORDER BY category,name',(cid,)).fetchall()
    return render_template('catalog.html',comp=comp,rows=rows)

def calculate_quote(form,comp):
    ids=form.getlist('item_id');qtys=form.getlist('quantity')
    with conn() as c: items={r['id']:dict(r) for r in c.execute('SELECT * FROM catalog WHERE company_id=? AND active=1',(comp['id'],))}
    chosen=[]
    for raw_id,raw_qty in zip(ids,qtys):
        try:id=int(raw_id)
        except:continue
        if id not in items:continue
        qty=num(raw_qty)
        if qty<=0:continue
        item=items[id];chosen.append(dict(id=id,name=item['name'],category=item['category'],quantity=qty,unit=item['unit'],unit_cost=item['cost'],subtotal=ri(qty*item['cost'])))
    other=num(form.get('other_cost'));freight=num(form.get('freight_cost'));labor=num(form.get('labor_cost'))
    cost=ri(sum(i['subtotal'] for i in chosen)+other+freight+labor)
    margin=min(90,num(form.get('margin',comp['margin']))) if session['user']['role']!='staff' else comp['margin']
    price=ri(cost/(1-margin/100)) if cost else 0
    pix=ri(price*(1-min(99,num(comp['pix_discount']))/100))
    card=ri(price/(1-min(95,num(comp['card_fee']))/100))
    return chosen,cost,price,pix,card

@app.route('/quotes',methods=['GET','POST'])
@login_required
def quotes():
    comp=current_company();cid=comp['id']
    if request.method=='POST':
        client_id=request.form.get('client_id',type=int)
        row_owned('clients',client_id,cid)
        chosen,cost,price,pix,card=calculate_quote(request.form,comp)
        due=request.form.get('estimated_delivery') or next_delivery(cid,comp['weekly_capacity'])
        with conn() as c:
            c.execute('''INSERT INTO quotes(company_id,client_id,description,dimensions,items_json,other_cost,freight_cost,labor_cost,total_cost,price,pix_price,card_price,estimated_delivery,notes)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(cid,client_id,request.form.get('description','Serviço de estofaria'),request.form.get('dimensions',''),json.dumps(chosen,ensure_ascii=False),num(request.form.get('other_cost')),num(request.form.get('freight_cost')),num(request.form.get('labor_cost')),cost,price,pix,card,due,request.form.get('notes','')))
        audit(cid,'Orçamento criado');flash('Orçamento gerado.');return redirect(url_for('quotes',company_id=cid))
    with conn() as c:
        rows=c.execute('SELECT q.*,cl.name client_name,cl.phone client_phone FROM quotes q JOIN clients cl ON cl.id=q.client_id WHERE q.company_id=? ORDER BY q.id DESC',(cid,)).fetchall()
        customers=c.execute('SELECT * FROM clients WHERE company_id=? ORDER BY name',(cid,)).fetchall()
        products=c.execute('SELECT * FROM catalog WHERE company_id=? AND active=1 ORDER BY category,name',(cid,)).fetchall()
    return render_template('quotes.html',comp=comp,rows=rows,customers=customers,products=products)

@app.route('/quotes/<int:id>',methods=['GET','POST'])
@login_required
def quote_detail(id):
    comp=current_company();cid=comp['id'];q=row_owned('quotes',id,cid)
    if request.method=='POST':
        status=request.form.get('status',q['status'])
        if status not in STATUSES:abort(400)
        paid=num(request.form.get('paid',q['paid']))
        actual_raw=request.form.get('actual_cost','')
        actual=(num(actual_raw) if actual_raw.strip() else None) if session['user']['role']!='staff' else q['actual_cost']
        actual_delivery=date.today().isoformat() if status=='Entregue' and not q['actual_delivery'] else q['actual_delivery']
        with conn() as c:c.execute('UPDATE quotes SET status=?,paid=?,actual_cost=?,actual_delivery=?,payment_method=?,notes=?,updated=CURRENT_TIMESTAMP WHERE id=? AND company_id=?',(status,paid,actual,actual_delivery,request.form.get('payment_method',q['payment_method']),request.form.get('notes',''),id,cid))
        audit(cid,f'Orçamento #{id}: {status}');flash('Atualizado.');return redirect(url_for('quote_detail',id=id,company_id=cid))
    with conn() as c:
        client=c.execute('SELECT * FROM clients WHERE id=? AND company_id=?',(q['client_id'],cid)).fetchone()
        docs=c.execute('SELECT * FROM documents WHERE quote_id=? AND company_id=? ORDER BY id DESC',(id,cid)).fetchall()
        linked=c.execute('SELECT * FROM costs WHERE quote_id=? AND company_id=?',(id,cid)).fetchall()
    return render_template('quote_detail.html',comp=comp,q=q,client=client,items=json.loads(q['items_json']),docs=docs,linked=linked)

@app.route('/visits',methods=['GET','POST'])
@login_required
def visits():
    comp=current_company();cid=comp['id']
    if request.method=='POST':
        client_id=request.form.get('client_id',type=int);row_owned('clients',client_id,cid)
        quote_id=request.form.get('quote_id',type=int)
        if quote_id:row_owned('quotes',quote_id,cid)
        starts=request.form.get('starts_at','');minutes=max(15,min(480,request.form.get('minutes',type=int) or 60))
        try:start=datetime.fromisoformat(starts)
        except:abort(400,'Data inválida')
        if start.weekday()>=5 or not (8<=start.hour<18) or start+timedelta(minutes=minutes)>start.replace(hour=18,minute=0):flash('Visitas: segunda a sexta, 8h às 18h.','error')
        else:
            with conn() as c:
                scheduled=c.execute("SELECT starts_at,minutes FROM visits WHERE company_id=? AND status='Agendada'",(cid,)).fetchall()
                conflict=any(start<datetime.fromisoformat(v['starts_at'])+timedelta(minutes=v['minutes']) and start+timedelta(minutes=minutes)>datetime.fromisoformat(v['starts_at']) for v in scheduled)
                if conflict:flash('Conflito: horário ocupado.','error')
                else:
                    c.execute('INSERT INTO visits(company_id,client_id,quote_id,starts_at,minutes,notes) VALUES(?,?,?,?,?,?)',(cid,client_id,quote_id,starts,minutes,request.form.get('notes','')))
                    flash('Visita agendada.');return redirect(url_for('visits',company_id=cid))
    with conn() as c:
        rows=c.execute('SELECT v.*,cl.name client_name FROM visits v JOIN clients cl ON cl.id=v.client_id WHERE v.company_id=? ORDER BY starts_at DESC',(cid,)).fetchall()
        customers=c.execute('SELECT * FROM clients WHERE company_id=? ORDER BY name',(cid,)).fetchall()
        qs=c.execute('SELECT * FROM quotes WHERE company_id=? ORDER BY id DESC',(cid,)).fetchall()
    return render_template('visits.html',comp=comp,rows=rows,customers=customers,qs=qs)

@app.route('/finance',methods=['GET','POST'])
@login_required
def finance():
    comp=current_company();cid=comp['id']
    if request.method=='POST':
        qid=request.form.get('quote_id',type=int)
        if qid:row_owned('quotes',qid,cid)
        with conn() as c:c.execute('INSERT INTO costs(company_id,quote_id,description,amount,date) VALUES(?,?,?,?,?)',(cid,qid,request.form['description'],num(request.form.get('amount')),request.form.get('date') or date.today().isoformat()))
        return redirect(url_for('finance',company_id=cid))
    with conn() as c:
        costs=c.execute('SELECT co.*,q.description job_name FROM costs co LEFT JOIN quotes q ON q.id=co.quote_id AND q.company_id=co.company_id WHERE co.company_id=? ORDER BY co.id DESC',(cid,)).fetchall()
        qs=c.execute('SELECT * FROM quotes WHERE company_id=? ORDER BY id DESC',(cid,)).fetchall()
    return render_template('finance.html',comp=comp,rows=costs,qs=qs)

@app.route('/settings',methods=['GET','POST'])
@role_required('admin','owner')
def settings():
    comp=current_company();cid=comp['id']
    if request.method=='POST':
        with conn() as c:c.execute('''UPDATE companies SET whatsapp=?,margin=?,pix_discount=?,card_fee=?,card_installments=?,weekly_capacity=?,commission_rate=?,lead_days=? WHERE id=?''',(
            request.form.get('whatsapp',''),min(90,num(request.form.get('margin'))),min(70,num(request.form.get('pix_discount'))),min(70,num(request.form.get('card_fee'))),max(1,min(12,request.form.get('card_installments',type=int) or 10)),max(1,request.form.get('weekly_capacity',type=int) or 1),min(100,num(request.form.get('commission_rate'))),max(0,request.form.get('lead_days',type=int) or 0),cid))
        flash('Configurações salvas.');return redirect(url_for('settings',company_id=cid))
    return render_template('settings.html',comp=comp)

@app.route('/users',methods=['GET','POST'])
@role_required('admin')
def users():
    if request.method=='POST':
        cid=request.form.get('company_id',type=int); role=request.form.get('role')
        if role not in ('admin','owner','staff') or (role!='admin' and cid not in (1,2)):abort(400)
        if role=='admin':cid=None
        password=request.form.get('password','')
        if len(password)<10:flash('A senha precisa ter pelo menos 10 caracteres.','error')
        else:
            try:
                with conn() as c:c.execute('INSERT INTO users(email,password,role,company_id) VALUES(?,?,?,?)',(request.form['email'].strip().lower(),generate_password_hash(password),role,cid))
                flash('Acesso criado.');return redirect(url_for('users'))
            except sqlite3.IntegrityError: flash('E-mail já cadastrado.','error')
    with conn() as c: rows=c.execute('SELECT u.*,co.name company_name FROM users u LEFT JOIN companies co ON co.id=u.company_id ORDER BY u.id').fetchall()
    return render_template('users.html',rows=rows)

@app.route('/documents/<int:quote_id>/<kind>')
@login_required
def pdf_document(quote_id,kind):
    comp=current_company();cid=comp['id'];q=row_owned('quotes',quote_id,cid)
    if kind not in ('orcamento','contrato','entrega'):abort(404)
    with conn() as c:cl=c.execute('SELECT * FROM clients WHERE id=? AND company_id=?',(q['client_id'],cid)).fetchone()
    output=io.BytesIO();p=canvas.Canvas(output,pagesize=A4);W,H=A4
    def line(txt,y,size=10):
        p.setFont('Helvetica',size)
        text=str(txt).encode('latin-1','replace').decode('latin-1')
        for j in range(0,len(text),94):
            p.drawString(46,y,text[j:j+94]);y-=16
        return y-7
    y=H-55;p.setFont('Helvetica-Bold',18);p.drawString(46,y,comp['name']);y-=40
    title={'orcamento':'ORÇAMENTO / ESTIMATIVA','contrato':'MODELO DE CONTRATO DE PRESTAÇÃO DE SERVIÇOS','entrega':'TERMO DE ENTREGA E RECEBIMENTO'}[kind]
    y=line(title,y,12);y-=8
    for s in [f'Ordem nº {q["id"]} - Emitido em {date.today().strftime("%d/%m/%Y")}',f'Cliente: {cl["name"]}   CPF: {cl["cpf"] or "Não informado"}',f'Contato: {cl["phone"]}  Endereço: {cl["address"]}',f'Serviço: {q["description"]}   Medidas: {q["dimensions"]}',f'Preço base: {money(q["price"])} | Pix: {money(q["pix_price"])} | Cartão: {money(q["card_price"])}',f'Previsão de entrega: {q["estimated_delivery"] or "A definir"}']:
        y=line(s,y)
    y-=15
    if kind=='contrato':
        clauses=['1. O prestador realizará o serviço descrito na ordem de serviço, conforme orçamento aprovado.',
        '2. Materiais, acabamentos, prazo e formas de pagamento serão os informados no orçamento.',
        '3. Alterações solicitadas pelo cliente deverão ser registradas e aprovadas antes de executar.',
        '4. O estado inicial do móvel será documentado por fotografias anexadas à ordem de serviço.',
        '5. A conclusão e entrega serão documentadas em termo de recebimento.',
        '6. Este é um modelo operacional; revise juridicamente antes de utilizá-lo com clientes.']
    elif kind=='entrega': clauses=['Declaro que recebi o móvel referente à ordem de serviço acima.', 'Observações sobre a entrega: ____________________________________________','______________________________________________________________________']
    else: clauses=['Valores sujeitos a confirmação após avaliação presencial, quando aplicável.','A aprovação definitiva e eventuais alterações devem ser registradas.']
    for s in clauses:y=line(s,y)
    y-=24
    for s in ['________________________________________','Assinatura do cliente e data','________________________________________','Representante da empresa e data']:
        y=line(s,y)
    p.setFont('Helvetica-Oblique',8);p.drawString(46,38,'Documentos e fotos complementares devem ser anexados ao cadastro da ordem.')
    p.showPage();p.save();output.seek(0)
    return send_file(output,as_attachment=True,download_name=f'{kind}_{quote_id}.pdf',mimetype='application/pdf')

@app.route('/upload/<int:quote_id>',methods=['POST'])
@login_required
def upload(quote_id):
    comp=current_company();cid=comp['id'];row_owned('quotes',quote_id,cid)
    f=request.files.get('file');kind=request.form.get('kind','outro')
    if kind not in ('antes','depois','contrato_assinado','termo_assinado','outro'):abort(400)
    if not f or not f.filename:abort(400)
    ext=os.path.splitext(secure_filename(f.filename))[1].lower()
    if ext not in ('.png','.jpg','.jpeg','.webp','.pdf'):abort(400,'Formato não permitido')
    os.makedirs(UPLOAD_DIR,exist_ok=True)
    filename=secrets.token_hex(16)+ext;f.save(os.path.join(UPLOAD_DIR,filename))
    with conn() as c:c.execute('INSERT INTO documents(company_id,quote_id,kind,filepath) VALUES(?,?,?,?)',(cid,quote_id,kind,filename))
    audit(cid,f'Anexo {kind} para serviço #{quote_id}')
    return redirect(url_for('quote_detail',id=quote_id,company_id=cid))

@app.route('/attachment/<int:id>')
@login_required
def attachment(id):
    comp=current_company();r=row_owned('documents',id,comp['id'])
    return send_from_directory(UPLOAD_DIR,r['filepath'],as_attachment=True)

@app.route('/audit')
@role_required('admin','owner')
def audit_page():
    comp=current_company()
    with conn() as c:rows=c.execute('SELECT * FROM logs WHERE company_id=? ORDER BY id DESC LIMIT 100',(comp['id'],)).fetchall()
    return render_template('audit.html',comp=comp,rows=rows)

if __name__=='__main__':
    init_db()
    app.run(host=os.environ.get('HOST','127.0.0.1'),port=int(os.environ.get('PORT',5000)),debug=False)
